"""
NullAI モデル管理API

LLMモデルの一覧取得、追加、更新、削除を行う。
HuggingFace Hubからのモデル検索・検証機能も提供。
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
import os
import asyncio
import aiohttp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.app.middleware.auth import get_current_user, get_current_user_optional, require_role, User
from backend.app.config import ConfigManager, ModelConfig, ModelProvider

router = APIRouter()

# グローバル設定マネージャー
_config_manager = None

# 人気モデルのプリセット
POPULAR_MODELS = [
    {"model_id": "deepseek-r1-7b", "model_name": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "display_name": "DeepSeek R1 7B", "size": "7B"},
    {"model_id": "deepseek-r1-14b", "model_name": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B", "display_name": "DeepSeek R1 14B", "size": "14B"},
    {"model_id": "deepseek-r1-32b", "model_name": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", "display_name": "DeepSeek R1 32B", "size": "32B"},
    {"model_id": "qwen2.5-7b", "model_name": "Qwen/Qwen2.5-7B-Instruct", "display_name": "Qwen 2.5 7B", "size": "7B"},
    {"model_id": "qwen2.5-14b", "model_name": "Qwen/Qwen2.5-14B-Instruct", "display_name": "Qwen 2.5 14B", "size": "14B"},
    {"model_id": "qwen2.5-32b", "model_name": "Qwen/Qwen2.5-32B-Instruct", "display_name": "Qwen 2.5 32B", "size": "32B"},
    {"model_id": "llama3.1-8b", "model_name": "meta-llama/Llama-3.1-8B-Instruct", "display_name": "Llama 3.1 8B", "size": "8B"},
    {"model_id": "llama3.2-3b", "model_name": "meta-llama/Llama-3.2-3B-Instruct", "display_name": "Llama 3.2 3B", "size": "3B"},
    {"model_id": "mistral-7b", "model_name": "mistralai/Mistral-7B-Instruct-v0.3", "display_name": "Mistral 7B", "size": "7B"},
    {"model_id": "phi3-mini", "model_name": "microsoft/Phi-3-mini-4k-instruct", "display_name": "Phi-3 Mini", "size": "3.8B"},
    {"model_id": "gemma2-9b", "model_name": "google/gemma-2-9b-it", "display_name": "Gemma 2 9B", "size": "9B"},
    {"model_id": "codellama-7b", "model_name": "codellama/CodeLlama-7b-Instruct-hf", "display_name": "CodeLlama 7B", "size": "7B"},
]


def get_config_manager() -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


# --- Pydanticスキーマ ---
class ModelCreate(BaseModel):
    model_id: str
    display_name: str
    provider: str  # huggingface, huggingface_api, local, gguf
    api_url: str = ""
    model_name: str = ""  # HuggingFaceモデルID or GGUFパス
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120
    is_default: bool = False
    supported_domains: List[str] = ["general"]
    description: str = ""


class ModelUpdate(BaseModel):
    display_name: Optional[str] = None
    api_url: Optional[str] = None
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    timeout: Optional[int] = None
    is_default: Optional[bool] = None
    supported_domains: Optional[List[str]] = None
    description: Optional[str] = None


class ModelResponse(BaseModel):
    model_id: str
    display_name: str
    provider: str
    api_url: str
    model_name: str
    max_tokens: int
    temperature: float
    timeout: int
    is_default: bool
    supported_domains: List[str]
    description: str


# --- APIエンドポイント ---
@router.get("/", response_model=List[ModelResponse])
async def list_models(
    domain_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    利用可能なモデル一覧を取得。
    domain_idを指定すると、そのドメインで使用可能なモデルのみを返す。
    """
    config = get_config_manager()
    models = config.list_models(domain_id=domain_id)

    return [
        ModelResponse(
            model_id=m.model_id,
            display_name=m.display_name,
            provider=m.provider.value,
            api_url=m.api_url,
            model_name=m.model_name,
            max_tokens=m.max_tokens,
            temperature=m.temperature,
            timeout=m.timeout,
            is_default=m.is_default,
            supported_domains=m.supported_domains,
            description=m.description
        )
        for m in models
    ]


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    current_user: User = Depends(get_current_user)
):
    """特定のモデル設定を取得"""
    config = get_config_manager()
    model = config.get_model(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    return ModelResponse(
        model_id=model.model_id,
        display_name=model.display_name,
        provider=model.provider.value,
        api_url=model.api_url,
        model_name=model.model_name,
        max_tokens=model.max_tokens,
        temperature=model.temperature,
        timeout=model.timeout,
        is_default=model.is_default,
        supported_domains=model.supported_domains,
        description=model.description
    )


@router.post("/", response_model=ModelResponse)
async def create_model(
    model: ModelCreate,
    current_user: User = Depends(require_role("admin"))
):
    """
    新しいモデルを追加。
    adminロールが必要。
    """
    config = get_config_manager()

    # プロバイダーの検証
    # 注意: OpenAI/Anthropic等の外部APIは利用規約上の理由からサポートされていません
    try:
        provider = ModelProvider(model.provider)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {model.provider}. Must be one of: huggingface, huggingface_api, local, gguf"
        )

    new_model = ModelConfig(
        model_id=model.model_id,
        display_name=model.display_name,
        provider=provider,
        api_url=model.api_url,
        model_name=model.model_name,
        max_tokens=model.max_tokens,
        temperature=model.temperature,
        timeout=model.timeout,
        is_default=model.is_default,
        supported_domains=model.supported_domains,
        description=model.description
    )

    if not config.add_model(new_model):
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model.model_id}' already exists"
        )

    return ModelResponse(
        model_id=new_model.model_id,
        display_name=new_model.display_name,
        provider=new_model.provider.value,
        api_url=new_model.api_url,
        model_name=new_model.model_name,
        max_tokens=new_model.max_tokens,
        temperature=new_model.temperature,
        timeout=new_model.timeout,
        is_default=new_model.is_default,
        supported_domains=new_model.supported_domains,
        description=new_model.description
    )


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    updates: ModelUpdate,
    current_user: User = Depends(require_role("admin"))
):
    """
    モデル設定を更新。
    adminロールが必要。
    """
    config = get_config_manager()
    existing = config.get_model(model_id)

    if not existing:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    # 更新を適用
    update_dict = updates.dict(exclude_unset=True)
    for key, value in update_dict.items():
        if hasattr(existing, key):
            setattr(existing, key, value)

    config.update_model(existing)

    return ModelResponse(
        model_id=existing.model_id,
        display_name=existing.display_name,
        provider=existing.provider.value,
        api_url=existing.api_url,
        model_name=existing.model_name,
        max_tokens=existing.max_tokens,
        temperature=existing.temperature,
        timeout=existing.timeout,
        is_default=existing.is_default,
        supported_domains=existing.supported_domains,
        description=existing.description
    )


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    current_user: User = Depends(require_role("admin"))
):
    """
    モデルを削除。
    adminロールが必要。
    """
    config = get_config_manager()

    if not config.delete_model(model_id):
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    return {"message": f"Model '{model_id}' deleted successfully"}


@router.get("/providers/info")
async def get_providers_info():
    """
    サポートされているプロバイダー情報を取得。
    どのプロバイダーが利用可能か、どれが削除されたかを確認できる。
    """
    from null_ai.model_router import ModelRouter
    config = get_config_manager()
    router = ModelRouter(config)
    return router.get_provider_info()


@router.post("/{model_id}/test")
async def test_model(
    model_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    モデルの接続テスト。
    簡単なプロンプトを送信して応答を確認する。
    """
    config = get_config_manager()
    model = config.get_model(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    # ModelRouterを使用してテスト
    from null_ai.model_router import ModelRouter
    model_router = ModelRouter(config)

    try:
        result = await model_router.infer(
            prompt="Hello, please respond with 'OK' if you can receive this message.",
            domain_id="general",
            model_id=model_id,
            save_to_memory=False,
            max_tokens=50
        )

        return {
            "status": "success",
            "model_id": model_id,
            "response": result.get("response", "")[:200],
            "latency_ms": result.get("latency_ms", 0)
        }

    except Exception as e:
        return {
            "status": "error",
            "model_id": model_id,
            "error": str(e)
        }


# --- HuggingFace Hub連携 ---

class HuggingFaceModelInfo(BaseModel):
    """HuggingFace Hubのモデル情報"""
    model_id: str
    model_name: str
    author: str
    downloads: int
    likes: int
    tags: List[str]
    pipeline_tag: Optional[str]
    is_gated: bool


class QuickAddRequest(BaseModel):
    """簡単追加リクエスト"""
    huggingface_model_name: str  # e.g., "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
    custom_model_id: Optional[str] = None  # カスタムID（省略時は自動生成）
    provider: str = "huggingface"  # huggingface or huggingface_api
    supported_domains: List[str] = ["general"]


@router.get("/huggingface/search")
async def search_huggingface_models(
    query: str = Query(..., description="検索クエリ"),
    limit: int = Query(20, ge=1, le=100),
    filter_type: str = Query("text-generation", description="モデルタイプでフィルタ")
):
    """
    HuggingFace Hubでモデルを検索。
    認証不要で誰でも利用可能。
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://huggingface.co/api/models"
            params = {
                "search": query,
                "limit": limit,
                "filter": filter_type,
                "sort": "downloads",
                "direction": "-1"
            }

            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    raise HTTPException(status_code=502, detail="HuggingFace API error")

                models = await response.json()

                return {
                    "query": query,
                    "count": len(models),
                    "models": [
                        {
                            "model_name": m.get("modelId", ""),
                            "author": m.get("author", ""),
                            "downloads": m.get("downloads", 0),
                            "likes": m.get("likes", 0),
                            "tags": m.get("tags", []),
                            "pipeline_tag": m.get("pipeline_tag"),
                            "is_gated": m.get("gated", False),
                            "last_modified": m.get("lastModified")
                        }
                        for m in models
                    ]
                }
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to HuggingFace: {str(e)}")


@router.get("/huggingface/validate/{model_name:path}")
async def validate_huggingface_model(
    model_name: str
):
    """
    HuggingFaceモデルの存在と互換性を検証。
    認証不要。
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://huggingface.co/api/models/{model_name}"

            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 404:
                    return {
                        "valid": False,
                        "model_name": model_name,
                        "error": "Model not found on HuggingFace Hub"
                    }

                if response.status != 200:
                    return {
                        "valid": False,
                        "model_name": model_name,
                        "error": f"HuggingFace API returned status {response.status}"
                    }

                model_info = await response.json()

                # テキスト生成モデルかどうかをチェック
                pipeline_tag = model_info.get("pipeline_tag", "")
                is_text_gen = pipeline_tag in ["text-generation", "text2text-generation", "conversational"]

                # ゲートモデル（アクセス申請が必要）かどうか
                is_gated = model_info.get("gated", False)

                # モデルサイズの推定（configファイルから）
                siblings = model_info.get("siblings", [])
                has_safetensors = any("safetensors" in s.get("rfilename", "") for s in siblings)
                has_pytorch = any("pytorch_model" in s.get("rfilename", "") or "model.safetensors" in s.get("rfilename", "") for s in siblings)

                return {
                    "valid": True,
                    "model_name": model_name,
                    "author": model_info.get("author", ""),
                    "pipeline_tag": pipeline_tag,
                    "is_text_generation": is_text_gen,
                    "is_gated": is_gated,
                    "downloads": model_info.get("downloads", 0),
                    "likes": model_info.get("likes", 0),
                    "tags": model_info.get("tags", []),
                    "has_safetensors": has_safetensors,
                    "has_pytorch": has_pytorch,
                    "warnings": [] if is_text_gen else ["This model may not be compatible with text generation"]
                }

    except aiohttp.ClientError as e:
        return {
            "valid": False,
            "model_name": model_name,
            "error": f"Failed to validate: {str(e)}"
        }


@router.get("/popular")
async def get_popular_models():
    """
    人気のHuggingFaceモデル一覧を取得。
    認証不要。
    """
    config = get_config_manager()

    # 既に追加済みのモデルをチェック
    existing_ids = set(config.models.keys())

    return {
        "models": [
            {
                **model,
                "already_added": model["model_id"] in existing_ids
            }
            for model in POPULAR_MODELS
        ]
    }


@router.post("/quick-add")
async def quick_add_model(
    request: QuickAddRequest,
    current_user: User = Depends(get_current_user)
):
    """
    HuggingFaceモデルを簡単に追加。
    認証済みユーザーなら誰でも利用可能（admin不要）。

    モデルは自動的に検証され、問題がなければ追加される。
    """
    config = get_config_manager()

    # HuggingFaceモデルを検証
    validation = None
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://huggingface.co/api/models/{request.huggingface_model_name}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 404:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Model '{request.huggingface_model_name}' not found on HuggingFace Hub"
                    )
                if response.status == 200:
                    validation = await response.json()
    except aiohttp.ClientError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to validate model: {str(e)}"
        )

    # ゲートモデルの警告
    if validation and validation.get("gated"):
        raise HTTPException(
            status_code=400,
            detail="This model requires access approval on HuggingFace. Please request access first."
        )

    # モデルIDを生成
    if request.custom_model_id:
        model_id = request.custom_model_id
    else:
        # huggingface_model_nameから自動生成
        model_id = request.huggingface_model_name.replace("/", "-").lower()

    # 既存チェック
    if config.get_model(model_id):
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_id}' already exists. Use a different custom_model_id."
        )

    # プロバイダーを検証
    try:
        provider = ModelProvider(request.provider)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {request.provider}. Use 'huggingface' or 'huggingface_api'"
        )

    # 表示名を生成
    display_name = validation.get("modelId", request.huggingface_model_name).split("/")[-1]

    # モデルを追加
    new_model = ModelConfig(
        model_id=model_id,
        display_name=display_name,
        provider=provider,
        model_name=request.huggingface_model_name,
        max_tokens=4096,
        temperature=0.7,
        timeout=120,
        is_default=False,
        supported_domains=request.supported_domains,
        description=f"Added from HuggingFace Hub by {current_user.display_name or current_user.id}"
    )

    config.add_model(new_model)

    return {
        "status": "success",
        "message": f"Model '{model_id}' added successfully",
        "model": {
            "model_id": model_id,
            "display_name": display_name,
            "provider": provider.value,
            "model_name": request.huggingface_model_name,
            "supported_domains": request.supported_domains
        }
    }


@router.post("/switch")
async def switch_active_model(
    model_id: str,
    domain_id: str = "general",
    current_user: User = Depends(get_current_user)
):
    """
    アクティブなモデルを切り替え。
    セッション単位で使用するモデルを変更できる。
    """
    config = get_config_manager()
    model = config.get_model(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    # ドメインの確認
    domain = config.get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    return {
        "status": "success",
        "active_model": {
            "model_id": model.model_id,
            "display_name": model.display_name,
            "provider": model.provider.value
        },
        "domain_id": domain_id,
        "message": f"Switched to {model.display_name} for {domain.name} domain"
    }
