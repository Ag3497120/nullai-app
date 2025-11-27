"""
Ilm-Athens 設定ファイル
HuggingFace公開版用

環境変数または直接設定で切り替え可能

注意:
- HuggingFace Transformersが推奨されるバックエンドです
- Ollamaは下位互換性のために残されていますが、非推奨です
- OpenAI/Anthropic等の外部APIは利用規約上の理由からサポートされていません
"""

import os
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InferenceBackend(Enum):
    """推論バックエンドの選択"""
    HUGGINGFACE = "huggingface"  # HuggingFace Transformers (推奨・ダウンロード追跡対応)
    HUGGINGFACE_API = "huggingface_api"  # HuggingFace Inference API
    GGUF = "gguf"                # GGUF形式 (llama.cpp)
    OLLAMA = "ollama"            # 非推奨: 下位互換性のためのみ


@dataclass
class IlmAthensConfig:
    """
    Ilm-Athens システム全体の設定

    HuggingFace公開版ではデフォルトでHuggingFaceバックエンドを使用し、
    モデルのダウンロード数が追跡されます。
    """

    # === 推論バックエンド設定 ===
    inference_backend: InferenceBackend = InferenceBackend.HUGGINGFACE

    # === HuggingFace設定 ===
    # モデルID - HuggingFace Hubからダウンロード
    hf_model_id: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"

    # 代替モデル（メモリが少ない場合）
    hf_model_id_small: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"

    # 量子化設定
    use_4bit_quantization: bool = True   # 4bit量子化（メモリ効率）
    use_8bit_quantization: bool = False  # 8bit量子化

    # Flash Attention
    use_flash_attention: bool = True

    # キャッシュディレクトリ
    cache_dir: Optional[str] = None

    # === Ollama設定（ローカル開発用） ===
    ollama_api_url: str = "http://localhost:11434"
    ollama_model_name: str = "deepseek-r1:32b"

    # === 生成パラメータ ===
    max_new_tokens: int = 2048
    default_temperature: float = 0.2
    top_p: float = 0.95

    # === ドメイン設定 ===
    default_domain: str = "medical"
    domain_schemas_path: str = "domain_schemas.json"

    # === 知識ベース設定 ===
    db_path: str = "ilm_athens_medical_db.iath"

    # === 倒木システム設定 ===
    enable_nurse_log_system: bool = False  # 継続学習システム
    succession_threshold: float = 0.85
    dream_interval_conversations: int = 10

    @classmethod
    def from_env(cls) -> "IlmAthensConfig":
        """環境変数から設定を読み込む"""
        config = cls()

        # バックエンド選択
        backend = os.getenv("ILM_INFERENCE_BACKEND", "huggingface").lower()
        if backend == "ollama":
            warnings.warn(
                "Ollamaバックエンドは非推奨です。HuggingFaceの使用を推奨します。",
                DeprecationWarning
            )
            config.inference_backend = InferenceBackend.OLLAMA
        elif backend == "huggingface_api":
            config.inference_backend = InferenceBackend.HUGGINGFACE_API
        elif backend == "gguf":
            config.inference_backend = InferenceBackend.GGUF

        # HuggingFace設定
        if model_id := os.getenv("ILM_HF_MODEL_ID"):
            config.hf_model_id = model_id

        if os.getenv("ILM_USE_SMALL_MODEL", "").lower() == "true":
            config.hf_model_id = config.hf_model_id_small

        if os.getenv("ILM_DISABLE_4BIT", "").lower() == "true":
            config.use_4bit_quantization = False

        # Ollama設定
        if ollama_url := os.getenv("ILM_OLLAMA_URL"):
            config.ollama_api_url = ollama_url

        if ollama_model := os.getenv("ILM_OLLAMA_MODEL"):
            config.ollama_model_name = ollama_model

        # キャッシュディレクトリ
        config.cache_dir = os.getenv("ILM_CACHE_DIR", None)

        return config

    def get_hf_config(self):
        """HuggingFaceエンジン用の設定を取得"""
        from ilm_athens_engine.deepseek_integration.hf_deepseek_engine import HFDeepSeekConfig

        return HFDeepSeekConfig(
            model_id=self.hf_model_id,
            max_new_tokens=self.max_new_tokens,
            temperature=self.default_temperature,
            top_p=self.top_p,
            load_in_4bit=self.use_4bit_quantization,
            load_in_8bit=self.use_8bit_quantization,
            use_flash_attention=self.use_flash_attention,
            cache_dir=self.cache_dir
        )

    def get_ollama_config(self):
        """Ollamaエンジン用の設定を取得"""
        from ilm_athens_engine.deepseek_integration.deepseek_runner import DeepSeekConfig

        return DeepSeekConfig(
            api_url=self.ollama_api_url,
            model_name=self.ollama_model_name,
            max_tokens=self.max_new_tokens,
            temperature=self.default_temperature,
            top_p=self.top_p
        )


# グローバル設定インスタンス
_config: Optional[IlmAthensConfig] = None


def get_config() -> IlmAthensConfig:
    """設定シングルトンを取得"""
    global _config
    if _config is None:
        _config = IlmAthensConfig.from_env()
    return _config


def set_config(config: IlmAthensConfig):
    """設定を上書き"""
    global _config
    _config = config
