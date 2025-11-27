"""
Ilm-Athens モデルマネージャー
モデルのライフサイクル管理と倒木システム対応

特徴:
- モデルのロード/アンロード管理
- 世代交代時のメモリ解放
- HuggingFace Transformersベースの推論
- シングルトンパターンによるリソース管理

注意:
- HuggingFace Transformersが推奨バックエンドです
- Ollamaは下位互換性のために残されていますが、非推奨です
- OpenAI/Anthropic等の外部APIはサポートされていません
"""

import gc
import logging
import threading
import weakref
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any, List, Callable
import torch

logger = logging.getLogger(__name__)


class EngineType(Enum):
    """推論エンジンの種類"""
    HUGGINGFACE = "huggingface"       # 推奨
    HUGGINGFACE_API = "huggingface_api"  # HuggingFace Inference API
    GGUF = "gguf"                     # llama.cpp互換
    OLLAMA = "ollama"                 # 非推奨（下位互換性のため）


@dataclass
class ModelGeneration:
    """モデル世代の情報"""
    generation_id: int
    engine_type: EngineType
    model_id: str
    created_at: float
    inference_count: int = 0
    is_active: bool = True


class ModelManager:
    """
    モデルのライフサイクルを管理するシングルトンマネージャー

    倒木システム（NurseLogSystem）と連携し、
    世代交代時に古いモデルを確実に解放する
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._engines: Dict[int, Any] = {}  # generation_id -> engine
        self._engine_refs: Dict[int, weakref.ref] = {}  # 弱参照
        self._generations: Dict[int, ModelGeneration] = {}
        self._current_generation_id = 0
        self._active_engine = None
        self._callbacks: List[Callable] = []
        self._initialized = True

        logger.info("ModelManager 初期化完了")

    def create_engine(
        self,
        engine_type: EngineType = EngineType.HUGGINGFACE,
        config: Optional[Any] = None,
        auto_load: bool = True
    ) -> Any:
        """
        新しい推論エンジンを作成

        Args:
            engine_type: エンジンタイプ
            config: エンジン設定
            auto_load: 自動でモデルをロードするか

        Returns:
            作成されたエンジン
        """
        import time

        self._current_generation_id += 1
        gen_id = self._current_generation_id

        logger.info(f"新しいエンジン作成: 世代 {gen_id}, タイプ {engine_type.value}")

        if engine_type == EngineType.HUGGINGFACE:
            from ilm_athens_engine.deepseek_integration.hf_deepseek_engine import (
                HFDeepSeekEngine, HFDeepSeekConfig
            )
            engine_config = config or HFDeepSeekConfig()
            engine = HFDeepSeekEngine(engine_config)
            model_id = engine_config.model_id
        else:
            from ilm_athens_engine.deepseek_integration.deepseek_runner import (
                DeepSeekR1Engine, DeepSeekConfig
            )
            engine_config = config or DeepSeekConfig()
            engine = DeepSeekR1Engine(engine_config)
            model_id = engine_config.model_name

        # 世代情報を記録
        generation = ModelGeneration(
            generation_id=gen_id,
            engine_type=engine_type,
            model_id=model_id,
            created_at=time.time()
        )
        self._generations[gen_id] = generation

        # エンジンを保存
        self._engines[gen_id] = engine
        self._engine_refs[gen_id] = weakref.ref(engine, self._on_engine_garbage_collected)

        # モデルをロード
        if auto_load and engine_type == EngineType.HUGGINGFACE:
            engine.load_model()

        return engine

    def _on_engine_garbage_collected(self, ref):
        """エンジンがGCで回収された時のコールバック"""
        logger.info("エンジンがガベージコレクションで回収されました")

    def switch_generation(self, new_engine: Any) -> Optional[Any]:
        """
        アクティブなエンジンを切り替え（倒木システム用）

        古いエンジンは完全にアンロードされ、参照が解除される

        Args:
            new_engine: 新しいアクティブエンジン

        Returns:
            以前のアクティブエンジン（既にアンロード済み）
        """
        old_engine = self._active_engine

        if old_engine is not None:
            logger.info("古いエンジンをアンロード中...")
            self._unload_engine(old_engine)

        self._active_engine = new_engine
        logger.info("エンジン切り替え完了")

        # コールバックを呼び出し
        for callback in self._callbacks:
            try:
                callback(old_engine, new_engine)
            except Exception as e:
                logger.error(f"切り替えコールバックエラー: {e}")

        return old_engine

    def _unload_engine(self, engine: Any):
        """
        エンジンを完全にアンロード

        倒木システムでの世代交代時に呼び出される
        """
        # HuggingFaceエンジンの場合
        if hasattr(engine, 'unload_model'):
            engine.unload_model()

        # 世代情報を非アクティブに
        for gen_id, gen_info in self._generations.items():
            if self._engines.get(gen_id) is engine:
                gen_info.is_active = False
                # エンジンへの参照を削除
                del self._engines[gen_id]
                break

        # 強制的にGC
        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        logger.info("エンジンアンロード完了")

    def retire_generation(self, generation_id: int):
        """
        特定の世代を引退させる（倒木更新）

        Args:
            generation_id: 引退させる世代ID
        """
        if generation_id not in self._generations:
            logger.warning(f"世代 {generation_id} は存在しません")
            return

        generation = self._generations[generation_id]
        engine = self._engines.get(generation_id)

        if engine is not None:
            logger.info(f"世代 {generation_id} を引退: {generation.inference_count}回の推論を実行")
            self._unload_engine(engine)

        generation.is_active = False

    def get_active_engine(self) -> Optional[Any]:
        """アクティブなエンジンを取得"""
        return self._active_engine

    def get_memory_status(self) -> Dict[str, Any]:
        """メモリ状況を取得"""
        status = {
            "active_generations": len([g for g in self._generations.values() if g.is_active]),
            "total_generations": len(self._generations),
            "gpu_memory_allocated_gb": 0.0,
            "gpu_memory_reserved_gb": 0.0,
        }

        if torch.cuda.is_available():
            status["gpu_memory_allocated_gb"] = torch.cuda.memory_allocated() / 1024**3
            status["gpu_memory_reserved_gb"] = torch.cuda.memory_reserved() / 1024**3

        return status

    def register_switch_callback(self, callback: Callable):
        """エンジン切り替え時のコールバックを登録"""
        self._callbacks.append(callback)

    def force_cleanup(self):
        """強制的に全リソースを解放"""
        logger.info("強制クリーンアップ開始")

        for gen_id in list(self._engines.keys()):
            engine = self._engines.get(gen_id)
            if engine is not None:
                self._unload_engine(engine)

        self._engines.clear()
        self._engine_refs.clear()
        self._active_engine = None

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("強制クリーンアップ完了")


# シングルトンインスタンスを取得
def get_model_manager() -> ModelManager:
    """ModelManagerのシングルトンインスタンスを取得"""
    return ModelManager()
