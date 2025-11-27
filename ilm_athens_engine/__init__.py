"""
Ilm-Athens: Hallucination-Free AI Medical Assistant

HuggingFacel‹H
DeepSeek R1 32B ’Ùü¹hW_;BûÕ‹ûLfyAI

(‹:
    from ilm_athens_engine import IlmAthensEngine
    from ilm_athens_engine.config import get_config

    config = get_config()
    engine = IlmAthensEngine(config)

    result = await engine.process_question(
        question="ÃK—^n:­ú–o",
        domain_id="medical"
    )
"""

__version__ = "0.1.0"
__author__ = "Ilm-Athens Team"

from .config import (
    IlmAthensConfig,
    InferenceBackend,
    get_config,
    set_config
)

from .model_manager import (
    ModelManager,
    EngineType,
    get_model_manager
)

from .deepseek_integration import (
    DeepSeekR1Engine,
    DeepSeekConfig,
    HFDeepSeekEngine,
    HFDeepSeekConfig,
    create_engine,
    DEEPSEEK_R1_32B_MODEL_ID,
    DEEPSEEK_R1_7B_MODEL_ID
)

# á¤ó¨ó¸ó¯é¹
from .inference_engine_deepseek_integrated import IlmAthensEngine

__all__ = [
    # Ðü¸çó
    "__version__",
    # -š
    "IlmAthensConfig",
    "InferenceBackend",
    "get_config",
    "set_config",
    # âÇë¡
    "ModelManager",
    "EngineType",
    "get_model_manager",
    # ¨Ö¨ó¸ó
    "DeepSeekR1Engine",
    "DeepSeekConfig",
    "HFDeepSeekEngine",
    "HFDeepSeekConfig",
    "create_engine",
    "DEEPSEEK_R1_32B_MODEL_ID",
    "DEEPSEEK_R1_7B_MODEL_ID",
    # á¤ó¨ó¸ó
    "IlmAthensEngine",
]
