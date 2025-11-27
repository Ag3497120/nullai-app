"""
NullAI - 汎用知識推論システム

マルチドメイン・マルチモデル対応の知識推論エンジン。
"""
__version__ = "1.0.0"
__name__ = "NullAI"

from null_ai.config import (
    ConfigManager,
    ModelConfig,
    DomainConfig,
    NullAIConfig,
    ModelProvider
)
from null_ai.model_router import ModelRouter

__all__ = [
    "ConfigManager",
    "ModelConfig",
    "DomainConfig",
    "NullAIConfig",
    "ModelProvider",
    "ModelRouter",
    "__version__",
    "__name__"
]
