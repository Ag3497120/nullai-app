"""
HuggingFace Transformers統合のDeepSeek R1推論エンジン
Ilm-Athens公開版用 - ダウンロード数追跡対応
"""

import asyncio
import gc
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, AsyncGenerator
import torch

logger = logging.getLogger(__name__)

# HuggingFace モデルID
DEEPSEEK_R1_32B_MODEL_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
DEEPSEEK_R1_7B_MODEL_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"


@dataclass
class HFDeepSeekConfig:
    """HuggingFace DeepSeek設定"""
    model_id: str = DEEPSEEK_R1_32B_MODEL_ID
    device_map: str = "auto"
    torch_dtype: str = "auto"  # "float16", "bfloat16", "auto"
    max_new_tokens: int = 2048
    temperature: float = 0.2
    top_p: float = 0.95
    do_sample: bool = True
    use_flash_attention: bool = True
    load_in_8bit: bool = False
    load_in_4bit: bool = True  # メモリ効率のためデフォルトで4bit量子化
    trust_remote_code: bool = True
    cache_dir: Optional[str] = None
    # モデルのロード状態追跡
    _model_loaded: bool = field(default=False, repr=False)


class HFDeepSeekEngine:
    """
    HuggingFace Transformersを使用したDeepSeek R1推論エンジン

    特徴:
    - HuggingFace Hubからの直接ダウンロード（ダウンロード数追跡）
    - 4bit/8bit量子化サポート
    - メモリ効率的なロード/アンロード
    - 倒木システム対応のモデル切り替え
    """

    _instance_count = 0  # アクティブなインスタンス数を追跡

    def __init__(self, config: Optional[HFDeepSeekConfig] = None):
        self.config = config or HFDeepSeekConfig()
        self.model = None
        self.tokenizer = None
        self._is_loaded = False
        self._generation_count = 0

        HFDeepSeekEngine._instance_count += 1
        self._instance_id = HFDeepSeekEngine._instance_count

        logger.info(f"HFDeepSeekEngine インスタンス #{self._instance_id} 作成")

    def load_model(self) -> bool:
        """
        モデルをHuggingFace Hubからロード

        Returns:
            bool: ロード成功かどうか
        """
        if self._is_loaded:
            logger.info("モデルは既にロード済みです")
            return True

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

            logger.info(f"モデルをロード中: {self.config.model_id}")
            print(f"📥 HuggingFaceからモデルをダウンロード中: {self.config.model_id}")
            print("   初回は時間がかかります。以降はキャッシュから読み込まれます。")

            # 量子化設定
            quantization_config = None
            if self.config.load_in_4bit:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
            elif self.config.load_in_8bit:
                quantization_config = BitsAndBytesConfig(load_in_8bit=True)

            # トークナイザーのロード
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_id,
                trust_remote_code=self.config.trust_remote_code,
                cache_dir=self.config.cache_dir
            )

            # モデルのロード
            model_kwargs = {
                "trust_remote_code": self.config.trust_remote_code,
                "device_map": self.config.device_map,
                "cache_dir": self.config.cache_dir,
            }

            if quantization_config:
                model_kwargs["quantization_config"] = quantization_config
            elif self.config.torch_dtype == "float16":
                model_kwargs["torch_dtype"] = torch.float16
            elif self.config.torch_dtype == "bfloat16":
                model_kwargs["torch_dtype"] = torch.bfloat16

            # Flash Attention 2の使用（対応GPUの場合）
            if self.config.use_flash_attention:
                try:
                    model_kwargs["attn_implementation"] = "flash_attention_2"
                except Exception:
                    logger.warning("Flash Attention 2は利用不可、標準のattentionを使用")

            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_id,
                **model_kwargs
            )

            self._is_loaded = True
            logger.info(f"✓ モデルロード完了: {self.config.model_id}")
            print(f"✓ モデルロード完了")

            # メモリ使用量をログ
            if torch.cuda.is_available():
                memory_gb = torch.cuda.max_memory_allocated() / 1024**3
                logger.info(f"  GPU メモリ使用量: {memory_gb:.2f} GB")
                print(f"  GPU メモリ使用量: {memory_gb:.2f} GB")

            return True

        except ImportError as e:
            logger.error(f"必要なライブラリがインストールされていません: {e}")
            print(f"❌ エラー: transformers, bitsandbytes をインストールしてください")
            print(f"   pip install transformers accelerate bitsandbytes")
            return False
        except Exception as e:
            logger.error(f"モデルロード失敗: {e}")
            print(f"❌ モデルロード失敗: {e}")
            return False

    def unload_model(self):
        """
        モデルをメモリから完全に解放
        倒木システムでの世代交代時に使用
        """
        logger.info(f"モデルをアンロード中 (インスタンス #{self._instance_id})")

        if self.model is not None:
            # モデルの参照を解除
            del self.model
            self.model = None

        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None

        self._is_loaded = False

        # GPUメモリを解放
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        # ガベージコレクションを強制実行
        gc.collect()

        logger.info(f"✓ モデルアンロード完了 (インスタンス #{self._instance_id})")

        if torch.cuda.is_available():
            memory_gb = torch.cuda.memory_allocated() / 1024**3
            logger.info(f"  解放後GPU メモリ: {memory_gb:.2f} GB")

    def __del__(self):
        """デストラクタでモデルを解放"""
        self.unload_model()
        HFDeepSeekEngine._instance_count -= 1

    async def infer(
        self,
        prompt: str,
        domain_context: Optional[Dict] = None,
        return_thinking: bool = True
    ) -> Dict[str, Any]:
        """
        推論を実行
        """
        import time
        start_time = time.time()

        # モデルがロードされていなければロード
        if not self._is_loaded:
            if not self.load_model():
                return {
                    "thinking": "",
                    "response": "モデルのロードに失敗しました",
                    "confidence": 0.0,
                    "error": "Model load failed",
                    "latency_ms": 0
                }

        # ドメインコンテキストからパラメータを取得
        domain_name = domain_context.get("domain_name", "general") if domain_context else "general"
        optimized_prompt = self._optimize_prompt(prompt, domain_context)

        try:
            # トークナイズ
            inputs = self.tokenizer(
                optimized_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=4096
            ).to(self.model.device)

            # 生成パラメータをドメインに応じて調整
            gen_params = self._get_generation_params(domain_name)

            # 推論実行（非同期ラップ）
            loop = asyncio.get_event_loop()
            outputs = await loop.run_in_executor(
                None,
                lambda: self.model.generate(
                    **inputs,
                    **gen_params,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            )

            # デコード
            full_text = self.tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )

            # レスポンスをパース
            result = self._parse_response(full_text, return_thinking)
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            result["domain"] = domain_name
            result["model_id"] = self.config.model_id

            self._generation_count += 1

            return result

        except Exception as e:
            logger.error(f"推論エラー: {e}")
            return {
                "thinking": "",
                "response": "",
                "confidence": 0.0,
                "error": str(e),
                "latency_ms": int((time.time() - start_time) * 1000),
                "domain": domain_name
            }

    def _get_generation_params(self, domain_name: str) -> Dict:
        """ドメイン別の生成パラメータを取得"""
        # ドメイン別の温度設定
        domain_temps = {
            "medical": 0.1,
            "legal": 0.15,
            "economics": 0.3,
            "general": 0.4
        }

        temperature = domain_temps.get(domain_name, self.config.temperature)

        return {
            "max_new_tokens": self.config.max_new_tokens,
            "temperature": temperature,
            "top_p": self.config.top_p,
            "do_sample": self.config.do_sample,
            "num_return_sequences": 1,
        }

    def _optimize_prompt(self, prompt: str, domain_context: Optional[Dict] = None) -> str:
        """プロンプトをドメインコンテキストで最適化"""
        if not domain_context:
            return prompt

        domain_name = domain_context.get("domain_name", "general")
        instructions = self._get_domain_instructions(domain_name)
        return f"{instructions}\n\n{prompt}"

    def _get_domain_instructions(self, domain_name: str) -> str:
        """ドメイン固有の指示を取得"""
        from .deepseek_runner import DeepSeekR1Engine
        # 既存の実装を再利用
        temp_engine = DeepSeekR1Engine.__new__(DeepSeekR1Engine)
        return temp_engine._get_domain_instructions(domain_name)

    def _parse_response(self, full_text: str, return_thinking: bool) -> Dict:
        """レスポンスをパース"""
        thinking, final_response = "", full_text

        if "<thinking>" in full_text and "</thinking>" in full_text:
            thinking_start = full_text.find("<thinking>") + len("<thinking>")
            thinking_end = full_text.find("</thinking>")
            thinking = full_text[thinking_start:thinking_end].strip()
            final_response = full_text[thinking_end + len("</thinking>"):].strip()

        confidence = self._estimate_confidence(thinking, final_response)

        return {
            "thinking": thinking if return_thinking else "",
            "response": final_response,
            "confidence": confidence,
            "full_response": full_text
        }

    def _estimate_confidence(self, thinking: str, response: str) -> float:
        """信頼度を推定"""
        confidence = 0.5

        if thinking:
            word_count = len(thinking.split())
            confidence += min(0.15, word_count / 800 * 0.15)

        # エビデンスレベル言及
        evidence_keywords = ["エビデンスレベル", "RCT", "メタ分析", "ガイドライン"]
        for kw in evidence_keywords:
            if kw in response:
                confidence += 0.05
                break

        # 構造化度
        structure_markers = ["【概要】", "【詳細説明】", "【注意事項】", "【参考】"]
        structure_count = sum(1 for m in structure_markers if m in response)
        confidence += min(0.1, structure_count * 0.025)

        return min(0.95, max(0.1, confidence))

    @property
    def is_loaded(self) -> bool:
        """モデルがロードされているか"""
        return self._is_loaded

    @property
    def generation_count(self) -> int:
        """生成回数"""
        return self._generation_count

    def get_memory_usage(self) -> Dict[str, float]:
        """メモリ使用量を取得（GB単位）"""
        result = {"cpu_allocated": 0.0, "gpu_allocated": 0.0, "gpu_reserved": 0.0}

        if torch.cuda.is_available():
            result["gpu_allocated"] = torch.cuda.memory_allocated() / 1024**3
            result["gpu_reserved"] = torch.cuda.memory_reserved() / 1024**3

        return result


# エンジンファクトリー関数
def create_engine(
    use_huggingface: bool = True,
    config: Optional[HFDeepSeekConfig] = None,
    ollama_config: Optional[Any] = None
):
    """
    適切な推論エンジンを作成

    Args:
        use_huggingface: TrueならHuggingFace版、FalseならOllama版
        config: HuggingFace用設定
        ollama_config: Ollama用設定

    Returns:
        推論エンジンインスタンス
    """
    if use_huggingface:
        return HFDeepSeekEngine(config)
    else:
        from .deepseek_runner import DeepSeekR1Engine, DeepSeekConfig
        return DeepSeekR1Engine(ollama_config or DeepSeekConfig())
