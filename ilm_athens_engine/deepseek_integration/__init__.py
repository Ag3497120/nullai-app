"""
Ilm-Athens DeepSeek統合モジュール

HuggingFace版（推奨）とOllama版の両方をサポート
"""

from .deepseek_runner import DeepSeekR1Engine, DeepSeekConfig, DOMAIN_PARAMETERS
from .hf_deepseek_engine import (
    HFDeepSeekEngine,
    HFDeepSeekConfig,
    DEEPSEEK_R1_32B_MODEL_ID,
    DEEPSEEK_R1_7B_MODEL_ID,
    create_engine
)

__all__ = [
    # Ollama版
    "DeepSeekR1Engine",
    "DeepSeekConfig",
    "DOMAIN_PARAMETERS",
    # HuggingFace版
    "HFDeepSeekEngine",
    "HFDeepSeekConfig",
    "DEEPSEEK_R1_32B_MODEL_ID",
    "DEEPSEEK_R1_7B_MODEL_ID",
    # ファクトリー
    "create_engine",
]
