"""
Knowledge Base API
知識タイル一覧表示と検証マーク機構
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import os
import json
import io
from sqlalchemy.orm import Session

from backend.app.middleware.auth import get_current_user_optional, get_current_user, User
from backend.app.config import settings
from backend.app.database.session import get_db
from backend.app.services.knowledge_service import KnowledgeService, get_knowledge_service

router = APIRouter()


# Pydanticモデルを更新
class VerificationMark(BaseModel):
    verification_type: str = "none"
    is_expert_verified: bool
    expert_orcid_id: Optional[str] = None
    expert_name: Optional[str] = None
    verification_date: Optional[datetime] = None
    verification_count: int = 0
    
    class Config:
        from_attributes = True

class KnowledgeTile(BaseModel):
    tile_id: str
    domain_id: str
    topic: str
    content_preview: str
    created_at: datetime
    updated_at: datetime
    verification_mark: VerificationMark
    contributor_id: Optional[str] = None
    confidence_score: float = 0.0
    tags: List[str] = []

    # ORMモデルからPydanticモデルへの変換を補助
    @classmethod
    def from_orm(cls, orm_obj):
        content_preview = orm_obj.content[:200] + "..." if len(orm_obj.content) > 200 else orm_obj.content
        
        is_expert_verified = orm_obj.verification_type in ["expert", "multi_expert"]
        expert_orcid = None
        expert_name = None
        if is_expert_verified and orm_obj.last_verified_by:
            expert_orcid = orm_obj.last_verified_by.orcid_id
            expert_name = orm_obj.last_verified_by.display_name

        verification_mark = VerificationMark(
            verification_type=orm_obj.verification_type,
            is_expert_verified=is_expert_verified,
            expert_orcid_id=expert_orcid,
            expert_name=expert_name,
            verification_date=orm_obj.last_verified_at,
            verification_count=orm_obj.verification_count
        )

        return cls(
            tile_id=orm_obj.id,
            domain_id=orm_obj.domain_id,
            topic=orm_obj.topic,
            content_preview=content_preview,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
            verification_mark=verification_mark,
            contributor_id=orm_obj.contributor_id,
            confidence_score=orm_obj.confidence_score,
            tags=orm_obj.tags or []
        )

class KnowledgeListResponse(BaseModel):
    tiles: List[KnowledgeTile]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class KnowledgeDetailResponse(BaseModel):
    tile: KnowledgeTile
    full_content: str
    sources: List[str] = []
    related_tiles: List[str] = []
    edit_history: List[dict] = []


class EditRequest(BaseModel):
    content: str
    edit_reason: Optional[str] = None


@router.get("/", response_model=KnowledgeListResponse)
async def list_knowledge_tiles(
    domain_id: Optional[str] = Query(None, description="ドメインでフィルタ"),
    verification_type: Optional[str] = Query(None, description="検証タイプでフィルタ"),
    search: Optional[str] = Query(None, description="検索クエリ"),
    page: int = Query(1, ge=1, description="ページ番号"),
    page_size: int = Query(20, ge=1, le=100, description="ページサイズ"),
    db: Session = Depends(get_db),
    service: KnowledgeService = Depends(get_knowledge_service)
):
    tiles_orm, total_count = service.list_tiles(
        db=db, page=page, page_size=page_size, 
        domain_id=domain_id, verification_type=verification_type, search=search
    )
    
    tiles_pydantic = [KnowledgeTile.from_orm(t) for t in tiles_orm]

    return KnowledgeListResponse(
        tiles=tiles_pydantic,
        total_count=total_count,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total_count
    )


@router.get("/{tile_id}", response_model=KnowledgeDetailResponse)
async def get_knowledge_tile(
    tile_id: str,
    db: Session = Depends(get_db),
    service: KnowledgeService = Depends(get_knowledge_service)
):
    tile_orm = service.get_tile(db, tile_id=tile_id)

    if not tile_orm:
        raise HTTPException(status_code=404, detail="Knowledge tile not found")
    
    tile_pydantic = KnowledgeTile.from_orm(tile_orm)

    return KnowledgeDetailResponse(
        tile=tile_pydantic,
        full_content=tile_orm.content,
        # TODO: Implement sources, related_tiles, and edit_history from DB
        sources=[],
        related_tiles=[],
        edit_history=[]
    )


@router.put("/{tile_id}", response_model=KnowledgeTile)
async def update_knowledge_tile(
    tile_id: str,
    request: EditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: KnowledgeService = Depends(get_knowledge_service)
):
    updated_tile_orm = service.update_tile(
        db=db, tile_id=tile_id, content=request.content, user=current_user
    )

    if not updated_tile_orm:
        raise HTTPException(status_code=404, detail="Knowledge tile not found")

    return KnowledgeTile.from_orm(updated_tile_orm)


@router.get("/export/json")
async def export_db_json(
    domain_id: Optional[str] = Query(None, description="特定ドメインのみエクスポート"),
    db: Session = Depends(get_db),
    service: KnowledgeService = Depends(get_knowledge_service)
):
    # Fetch all tiles for export
    tiles_orm, _ = service.list_tiles(db=db, page_size=10000, domain_id=domain_id) # A large page size to get all
    tiles_pydantic = [KnowledgeTile.from_orm(t).dict() for t in tiles_orm]

    export_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "source": "NullAI Knowledge Base",
            "domain_filter": domain_id or "all",
            "tile_count": len(tiles_pydantic)
        },
        "tiles": tiles_pydantic
    }

    json_str = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)

    return StreamingResponse(
        io.BytesIO(json_str.encode('utf-8')),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=null_ai_knowledge_{datetime.now().strftime('%Y%m%d')}.json"
        }
    )
