from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import os

from backend.app.middleware.auth import (
    get_current_user, get_current_user_optional, get_user_or_guest,
    require_role, require_expert, User, GuestUser
)

router = APIRouter()

DOMAIN_SCHEMAS_PATH = "domain_schemas.json"


class DomainAxis(BaseModel):
    name: str
    description: str
    keywords: List[str]


class DomainSchema(BaseModel):
    domain_id: str
    name: str
    description: str
    axes: List[DomainAxis]


class DomainListResponse(BaseModel):
    domains: List[Dict[str, Any]]


def load_schemas() -> Dict:
    """ドメインスキーマファイルを読み込む"""
    if os.path.exists(DOMAIN_SCHEMAS_PATH):
        with open(DOMAIN_SCHEMAS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"domains": {}}


def save_schemas(schemas: Dict):
    """ドメインスキーマファイルを保存"""
    with open(DOMAIN_SCHEMAS_PATH, 'w', encoding='utf-8') as f:
        json.dump(schemas, f, ensure_ascii=False, indent=2)


@router.get("/", response_model=DomainListResponse)
async def list_domains(
    current_user: User = Depends(get_user_or_guest)
):
    """利用可能なドメイン一覧を取得（ゲストアクセス可）"""
    schemas = load_schemas()
    domains = []

    for domain_id, schema in schemas.get("domains", {}).items():
        domains.append({
            "domain_id": domain_id,
            "name": schema.get("name", domain_id),
            "description": schema.get("description", ""),
            "axis_count": len(schema.get("axes", []))
        })

    return {"domains": domains}


@router.get("/{domain_id}")
async def get_domain(
    domain_id: str,
    current_user: User = Depends(get_user_or_guest)
):
    """特定のドメインスキーマを取得（ゲストアクセス可）"""
    schemas = load_schemas()

    if domain_id not in schemas.get("domains", {}):
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    schema = schemas["domains"][domain_id]
    return {
        "domain_id": domain_id,
        **schema
    }


@router.put("/{domain_id}")
async def update_domain(
    domain_id: str,
    domain: DomainSchema,
    current_user: User = Depends(require_role("editor"))
):
    """
    ドメインスキーマを更新（または新規作成）。
    editorまたはadminロールが必要。
    """
    schemas = load_schemas()

    if "domains" not in schemas:
        schemas["domains"] = {}

    schemas["domains"][domain_id] = {
        "name": domain.name,
        "description": domain.description,
        "axes": [
            {
                "name": axis.name,
                "description": axis.description,
                "keywords": axis.keywords
            }
            for axis in domain.axes
        ]
    }

    save_schemas(schemas)

    return {
        "message": f"Domain '{domain_id}' updated successfully",
        "domain_id": domain_id,
        "updated_by": current_user.id
    }


@router.delete("/{domain_id}")
async def delete_domain(
    domain_id: str,
    current_user: User = Depends(require_role("admin"))
):
    """ドメインを削除（adminのみ）"""
    schemas = load_schemas()

    if domain_id not in schemas.get("domains", {}):
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    # 基本ドメインは削除不可
    protected_domains = ["medical", "legal", "economics"]
    if domain_id in protected_domains:
        raise HTTPException(status_code=403, detail=f"Cannot delete protected domain '{domain_id}'")

    del schemas["domains"][domain_id]
    save_schemas(schemas)

    return {
        "message": f"Domain '{domain_id}' deleted successfully",
        "deleted_by": current_user.id
    }
