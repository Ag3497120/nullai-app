"""
NullAI 推論サービス

HuggingFace Transformersベースの推論エンジンを使用。
ストリーミング対応。
"""
import asyncio
import json
from typing import AsyncGenerator, Dict, Any, Optional
from fastapi import Depends
import sys
import os
import logging
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__) # Moved to top

# プロジェクトルートをsys.pathに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# --- ストリーミング用のキュー管理 ---
_streaming_queues: Dict[str, Queue] = {}


class StreamingCallback:
    """HuggingFace Transformersのストリーミングコールバック"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.queue = Queue()
        _streaming_queues[session_id] = self.queue
        self.finished = False

    def on_token(self, token: str):
        """トークンが生成されるたびに呼ばれる"""
        if not self.finished:
            self.queue.put({"type": "token", "content": token})

    def on_thinking(self, thinking: str):
        """思考プロセスが生成されたとき"""
        self.queue.put({"type": "thinking", "content": thinking})

    def on_finish(self, response: str):
        """生成完了時"""
        self.queue.put({"type": "complete", "content": response})
        self.finished = True
        self.queue.put(None)  # 終了シグナル

    def on_error(self, error: str):
        """エラー発生時"""
        self.queue.put({"type": "error", "content": error})
        self.finished = True
        self.queue.put(None)

    def cleanup(self):
        """クリーンアップ"""
        if self.session_id in _streaming_queues:
            del _streaming_queues[self.session_id]


# --- 推論エンジン ---
_inference_engine = None


def get_inference_engine():
    """推論エンジンを取得（遅延初期化）"""
    global _inference_engine
    if _inference_engine is None:
        try:
            from null_ai.config import ConfigManager
            from null_ai.model_router import ModelRouter

            logger.info("Initializing NullAI ModelRouter...")
            config = ConfigManager()
            _inference_engine = ModelRouter(config)
            logger.info("ModelRouter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ModelRouter: {e}")
            # フォールバック: 旧エンジンを試す
            try:
                from ilm_athens_engine.inference_engine_deepseek_integrated import IlmAthensEngine
                from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekConfig
                from ilm_athens_engine.domain.manager import DomainManager
                from backend.iath_db_interface import IathDBInterface

                logger.warning("Falling back to legacy IlmAthensEngine")
                deepseek_config = DeepSeekConfig(
                    api_url=getattr(settings, 'DEEPSEEK_API_URL', 'http://localhost:11434'),
                    model_name=getattr(settings, 'DEEPSEEK_MODEL_NAME', 'deepseek-r1:32b')
                )
                db_path = getattr(settings, 'DB_PATH', 'ilm_athens_medical_db.iath')

                domain_manager = DomainManager("domain_schemas.json")
                db_interface = IathDBInterface(db_file_path=db_path)
                db_interface.load_db()

                _inference_engine = IlmAthensEngine(
                    domain_manager=domain_manager,
                    db_interface=db_interface,
                    deepseek_config=deepseek_config
                )
            except Exception as e2:
                logger.error(f"Failed to initialize fallback engine: {e2}")
                raise RuntimeError(f"No inference engine available: {e}, {e2}")

    return _inference_engine


class InferenceService:
    """推論サービス（HuggingFace Transformers対応）"""

    def __init__(self, cache_service: CacheService):
        self.cache = cache_service
        self._engine = None

        # NurseLog System initialization
        if NURSELOG_AVAILABLE:
            self.inference_history = InferenceHistory(storage_path="inference_history")
            self.succession_manager = None  # Lazy initialization
            logger.info("NurseLog System enabled for inference tracking")
        else:
            self.inference_history = None
            self.succession_manager = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = get_inference_engine()
        return self._engine

    async def process_question(
        self,
        question: str,
        user_id: str,
        session_id: str,
        domain_id: str,
        model_id: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        質問を処理して回答を生成

        Args:
            question: 質問テキスト
            user_id: ユーザーID
            session_id: セッションID
            domain_id: ドメインID
            model_id: 使用するモデルID（オプション）
            temperature: 温度パラメータ（オプション）

        Returns:
            推論結果の辞書
        """
        # キャッシュチェック
        cache_key = f"inference:{domain_id}:{hash(question)}"
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for question: {question[:50]}...")
            return cached_result

        logger.info(f"Processing question: {question[:50]}... (domain={domain_id})")

        try:
            # NullAI ModelRouterを使用
            if hasattr(self.engine, 'infer'):
                result = await self.engine.infer(
                    prompt=question,
                    domain_id=domain_id,
                    model_id=model_id,
                    temperature=temperature,
                    save_to_memory=True
                )

                # レスポンスを標準形式に変換
                response = {
                    "status": "success",
                    "answer": result.get("response", ""),
                    "thinking": result.get("thinking", ""),
                    "confidence": result.get("confidence", 0.5),
                    "model_used": result.get("model_name", "unknown"),
                    "latency_ms": result.get("latency_ms", 0),
                    "saved_to_memory": result.get("saved_to_memory", False)
                }
            else:
                # レガシーエンジン（IlmAthensEngine）
                result = await self.engine.process_question(
                    question=question,
                    session_id=session_id,
                    domain_id=domain_id
                )
                response = result

            # キャッシュに保存
            if response.get("status") == "success":
                await self.cache.set(cache_key, response, ttl=3600)

                # NurseLog System: Save inference to history for future training
                if self.inference_history and response.get("confidence", 0) >= 0.5:
                    try:
                        inference_id = self.inference_history.save_inference(
                            question=question,
                            response=response.get("answer", ""),
                            domain_id=domain_id,
                            model_name=response.get("model_used", "unknown"),
                            confidence=response.get("confidence", 0.5),
                            thinking_process=response.get("thinking"),
                            metadata={
                                "user_id": user_id,
                                "session_id": session_id,
                                "latency_ms": response.get("latency_ms", 0)
                            }
                        )
                        response["inference_id"] = inference_id
                        logger.info(f"Saved inference to history: {inference_id}")
                    except Exception as e:
                        logger.error(f"Failed to save inference to history: {e}")

            return response

        except Exception as e:
            logger.error(f"Inference error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "answer": "",
                "confidence": 0.0
            }

    async def stream_tokens(
        self,
        session_id: str,
        question: Optional[str] = None,
        domain_id: str = "general",
        model_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        トークンをストリーミングで生成

        Args:
            session_id: セッションID
            question: 質問（指定された場合は新規生成開始）
            domain_id: ドメインID
            model_id: モデルID

        Yields:
            トークンまたはステータスメッセージ
        """
        # 新しい質問の場合、バックグラウンドで生成開始
        if question:
            callback = StreamingCallback(session_id)

            # バックグラウンドスレッドで生成を実行
            def generate_in_background():
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    # HuggingFace Transformersのストリーミング生成
                    if hasattr(self.engine, '_hf_inference'):
                        # HuggingFaceInferenceクラスを使用
                        hf = self.engine._hf_inference
                        hf._ensure_dependencies()

                        model_config = None
                        if model_id:
                            model_config = self.engine.config.get_model(model_id)
                        if not model_config:
                            model_config = self.engine.get_model_for_domain(domain_id)

                        if not model_config:
                            callback.on_error("No model available")
                            return

                        model_data = hf.load_model(model_config.model_name)
                        model = model_data["model"]
                        tokenizer = model_data["tokenizer"]

                        # チャット形式のプロンプト構築
                        if hasattr(tokenizer, "apply_chat_template"):
                            messages = [{"role": "user", "content": question}]
                            input_text = tokenizer.apply_chat_template(
                                messages,
                                tokenize=False,
                                add_generation_prompt=True
                            )
                        else:
                            input_text = question

                        inputs = tokenizer(input_text, return_tensors="pt")
                        if hf._device != "cpu":
                            inputs = {k: v.to(model.device) for k, v in inputs.items()}

                        # TextIteratorStreamerを使用
                        try:
                            from transformers import TextIteratorStreamer
                            streamer = TextIteratorStreamer(
                                tokenizer,
                                skip_prompt=True,
                                skip_special_tokens=True
                            )

                            generation_kwargs = {
                                **inputs,
                                "max_new_tokens": model_config.max_tokens,
                                "temperature": model_config.temperature,
                                "do_sample": model_config.temperature > 0,
                                "streamer": streamer
                            }

                            # 別スレッドで生成
                            import threading
                            thread = threading.Thread(
                                target=model.generate,
                                kwargs=generation_kwargs
                            )
                            thread.start()

                            # ストリーマーからトークンを取得
                            generated_text = ""
                            for token in streamer:
                                callback.on_token(token)
                                generated_text += token

                            thread.join()
                            callback.on_finish(generated_text)

                        except ImportError:
                            # TextIteratorStreamerが使えない場合は通常生成
                            logger.warning("TextIteratorStreamer not available, using non-streaming generation")
                            result = hf._generate_sync(
                                model_config.model_name,
                                question,
                                model_config.max_tokens,
                                model_config.temperature
                            )
                            callback.on_finish(result.get("response", ""))

                    else:
                        # レガシーエンジンの場合
                        result = loop.run_until_complete(
                            self.engine.process_question(
                                question=question,
                                session_id=session_id,
                                domain_id=domain_id
                            )
                        )
                        answer = result.get("answer", result.get("response", ""))
                        callback.on_finish(answer)

                except Exception as e:
                    logger.error(f"Streaming generation error: {e}")
                    callback.on_error(str(e))
                finally:
                    callback.cleanup()

            # バックグラウンドスレッドを開始
            thread = threading.Thread(target=generate_in_background, daemon=True)
            thread.start()

            # 初期メッセージ
            yield {"type": "start", "message": "生成を開始しました"}

        # キューからトークンを取得してyield
        queue = _streaming_queues.get(session_id)
        if not queue:
            yield {"type": "error", "message": "セッションが見つかりません"}
            return

        while True:
            try:
                # 0.1秒のタイムアウトでキューからアイテムを取得
                item = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: queue.get(timeout=0.1)
                )

                if item is None:
                    # 終了シグナル
                    break

                yield item

                if item.get("type") in ["complete", "error"]:
                    break

            except Empty:
                # タイムアウト - 接続維持のためのハートビート
                yield {"type": "heartbeat"}
                continue
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield {"type": "error", "message": str(e)}
                break

    def get_succession_manager(self) -> Optional[ModelSuccessionManager]:
        """Get or initialize succession manager"""
        if not NURSELOG_AVAILABLE or not self.inference_history:
            return None

        if self.succession_manager is None:
            exporter = TrainingDataExporter(output_dir="training_data")
            self.succession_manager = ModelSuccessionManager(
                history_manager=self.inference_history,
                exporter=exporter,
                succession_threshold=1000
            )

        return self.succession_manager

    async def check_succession_status(self) -> Dict[str, Any]:
        """Check if model succession should be triggered"""
        manager = self.get_succession_manager()
        if not manager:
            return {
                "status": "unavailable",
                "message": "NurseLog System not available"
            }

        should_trigger = manager.check_succession_trigger()
        history = self.inference_history.load_history(min_confidence=0.8)

        return {
            "status": "ready" if should_trigger else "not_ready",
            "should_trigger": should_trigger,
            "high_quality_count": len(history),
            "threshold": manager.succession_threshold,
            "message": "Ready for succession" if should_trigger else "Not enough high-quality inferences"
        }

    async def trigger_succession(
        self,
        domain_id: Optional[str] = None,
        min_confidence: float = 0.8,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Trigger model succession and export training data"""
        manager = self.get_succession_manager()
        if not manager:
            return {
                "status": "error",
                "message": "NurseLog System not available"
            }

        logger.info(f"Triggering model succession for domain: {domain_id or 'all'}")

        try:
            # Prepare succession (export training data)
            result = await manager.prepare_succession(
                domain_id=domain_id,
                min_confidence=min_confidence
            )

            # Create DB snapshot if path provided
            if db_path and os.path.exists(db_path):
                from null_ai.nurse_log_system import DBArchiveManager
                archive_manager = DBArchiveManager(archive_dir="db_archives")
                succession_history = manager.get_succession_history()
                generation = len(succession_history)

                snapshot_path = archive_manager.create_snapshot(
                    db_path=db_path,
                    generation=generation,
                    metadata={"succession_result": result}
                )
                result["db_snapshot"] = snapshot_path

            return result

        except Exception as e:
            logger.error(f"Succession trigger failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


async def get_inference_service(
    cache_service: CacheService = Depends(get_cache_service)
) -> InferenceService:
    """依存性注入用のファクトリ関数"""
    return InferenceService(cache_service=cache_service)
