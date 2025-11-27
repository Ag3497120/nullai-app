"""
NullAI システムステータスAPI

システムの状態、モデルの可用性、DB接続状況などを取得する。
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import sys
import os
import platform
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

router = APIRouter()


class SystemStatus(BaseModel):
    """システムステータスのレスポンスモデル"""
    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    timestamp: str
    environment: Dict[str, Any]
    services: Dict[str, Dict[str, Any]]
    models: Dict[str, Any]


def check_gpu_status() -> Dict[str, Any]:
    """GPU状況を確認"""
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        mps_available = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

        result = {
            "cuda_available": cuda_available,
            "mps_available": mps_available,
            "device": "cuda" if cuda_available else ("mps" if mps_available else "cpu")
        }

        if cuda_available:
            result["cuda_device_count"] = torch.cuda.device_count()
            result["cuda_device_name"] = torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else None
            result["cuda_memory_allocated_gb"] = round(torch.cuda.memory_allocated() / 1024**3, 2)
            result["cuda_memory_cached_gb"] = round(torch.cuda.memory_reserved() / 1024**3, 2)

        return result
    except ImportError:
        return {"error": "PyTorch not installed", "cuda_available": False, "mps_available": False, "device": "cpu"}
    except Exception as e:
        return {"error": str(e), "cuda_available": False, "mps_available": False, "device": "cpu"}


def check_transformers_status() -> Dict[str, Any]:
    """HuggingFace Transformersの状況を確認"""
    try:
        import transformers
        return {
            "available": True,
            "version": transformers.__version__
        }
    except ImportError:
        return {"available": False, "error": "transformers not installed"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_database_status() -> Dict[str, Any]:
    """データベースの状況を確認"""
    try:
        from backend.app.database.session import SessionLocal
        db = SessionLocal()
        # 簡単なクエリでDB接続を確認
        db.execute("SELECT 1")
        db.close()
        return {"available": True, "type": "sqlite"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_model_router_status() -> Dict[str, Any]:
    """ModelRouterの状況を確認"""
    try:
        from null_ai.config import ConfigManager
        from null_ai.model_router import ModelRouter

        config = ConfigManager()
        router = ModelRouter(config)

        models = config.list_models()
        default_model = config.get_default_model()

        return {
            "available": True,
            "total_models": len(models),
            "default_model": default_model.model_id if default_model else None,
            "supported_providers": ["huggingface", "huggingface_api", "local", "gguf"],
            "models": [
                {
                    "id": m.model_id,
                    "name": m.display_name,
                    "provider": m.provider.value,
                    "is_default": m.is_default
                }
                for m in models
            ]
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """
    システムの全体的なステータスを取得。

    - 環境情報（Python版、OS等）
    - GPU状況
    - HuggingFace Transformers状況
    - データベース接続状況
    - モデル設定状況
    """
    # 各サービスの状況を確認
    gpu_status = check_gpu_status()
    transformers_status = check_transformers_status()
    db_status = check_database_status()
    model_status = check_model_router_status()

    # 全体的なステータスを判定
    all_healthy = (
        transformers_status.get("available", False) and
        db_status.get("available", False) and
        model_status.get("available", False)
    )

    if all_healthy:
        overall_status = "healthy"
    elif transformers_status.get("available", False) or model_status.get("available", False):
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return SystemStatus(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        environment={
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "system": platform.system(),
            "processor": platform.processor()
        },
        services={
            "gpu": gpu_status,
            "transformers": transformers_status,
            "database": db_status
        },
        models=model_status
    )


@router.get("/health")
async def health_check():
    """軽量なヘルスチェック"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/providers")
async def get_supported_providers():
    """
    サポートされているLLMプロバイダー情報を取得。
    どのプロバイダーが使用可能か、どれが削除されたかを表示。
    """
    return {
        "supported": [
            {
                "id": "huggingface",
                "name": "HuggingFace Transformers",
                "description": "ローカルでモデルをダウンロードして実行。GPU推奨。",
                "requires_api_key": False,
                "requires_gpu": True
            },
            {
                "id": "huggingface_api",
                "name": "HuggingFace Inference API",
                "description": "HuggingFaceのサーバーで推論。無料枠あり。",
                "requires_api_key": False,
                "requires_gpu": False
            },
            {
                "id": "local",
                "name": "Local Model",
                "description": "ローカルにダウンロード済みのモデルを使用。",
                "requires_api_key": False,
                "requires_gpu": True
            },
            {
                "id": "gguf",
                "name": "GGUF (llama.cpp)",
                "description": "量子化モデル。CPU環境でも動作可能。",
                "requires_api_key": False,
                "requires_gpu": False
            }
        ],
        "unsupported": [
            {
                "id": "openai",
                "reason": "利用規約上、競合モデル作成への使用が禁止されているため削除されました。"
            },
            {
                "id": "anthropic",
                "reason": "利用規約上、競合モデル作成への使用が禁止されているため削除されました。"
            },
            {
                "id": "ollama",
                "reason": "HuggingFaceでの公開を考慮し、直接Transformersを使用する方式に変更されました。"
            }
        ]
    }
