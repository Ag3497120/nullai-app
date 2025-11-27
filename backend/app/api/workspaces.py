"""
ワークスペース管理API - マルチテナントDB機能
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import os
import re

from backend.app.database.session import get_db
from backend.app.database.models import Workspace, WorkspaceMember, User
from backend.app.middleware.auth import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class WorkspaceCreate(BaseModel):
    """ワークスペース作成リクエスト"""
    name: str
    description: Optional[str] = None
    is_public: bool = False
    allow_guest_edit: bool = True
    allow_guest_view: bool = True


class WorkspaceUpdate(BaseModel):
    """ワークスペース更新リクエスト"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    allow_guest_edit: Optional[bool] = None
    allow_guest_view: Optional[bool] = None


class WorkspaceResponse(BaseModel):
    """ワークスペースレスポンス"""
    id: str
    name: str
    slug: str
    description: Optional[str]
    owner_id: str
    is_public: bool
    allow_guest_edit: bool
    allow_guest_view: bool
    tile_count: int
    domain_count: int
    member_count: int
    created_at: str

    class Config:
        from_attributes = True


class WorkspaceMemberResponse(BaseModel):
    """ワークスペースメンバーレスポンス"""
    id: str
    user_id: str
    username: str
    display_name: Optional[str]
    role: str
    can_read: bool
    can_write: bool
    can_delete: bool
    joined_at: str


# ===== ワークスペース管理 =====

@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    include_public: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ユーザーのワークスペース一覧を取得
    - 自分が所有するワークスペース
    - メンバーとして参加しているワークスペース
    - 公開ワークスペース（オプション）
    """
    workspaces = []

    # 所有ワークスペース
    owned = db.query(Workspace).filter(Workspace.owner_id == current_user.id).all()
    workspaces.extend(owned)

    # メンバーとして参加しているワークスペース
    member_records = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == current_user.id).all()
    for member in member_records:
        workspaces.append(member.workspace)

    # 公開ワークスペース
    if include_public:
        public = db.query(Workspace).filter(Workspace.is_public == True).all()
        workspaces.extend(public)

    # 重複を削除
    unique_workspaces = {ws.id: ws for ws in workspaces}.values()

    return [WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        description=ws.description,
        owner_id=ws.owner_id,
        is_public=ws.is_public,
        allow_guest_edit=ws.allow_guest_edit,
        allow_guest_view=ws.allow_guest_view,
        tile_count=ws.tile_count,
        domain_count=ws.domain_count,
        member_count=ws.member_count,
        created_at=ws.created_at.isoformat()
    ) for ws in unique_workspaces]


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """新しいワークスペースを作成"""
    # slugを生成（URLフレンドリーな形式）
    base_slug = re.sub(r'[^a-z0-9-]', '-', workspace_data.name.lower())
    base_slug = re.sub(r'-+', '-', base_slug).strip('-')
    
    # 重複チェック
    slug = base_slug
    counter = 1
    while db.query(Workspace).filter(Workspace.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    # ワークスペースディレクトリを作成
    workspace_dir = "workspaces"
    os.makedirs(workspace_dir, exist_ok=True)

    workspace = Workspace(
        name=workspace_data.name,
        slug=slug,
        description=workspace_data.description,
        owner_id=current_user.id,
        is_public=workspace_data.is_public,
        allow_guest_edit=workspace_data.allow_guest_edit,
        allow_guest_view=workspace_data.allow_guest_view,
        db_type="sqlite",
        db_path=f"{workspace_dir}/{slug}.db"
    )

    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    logger.info(f"Workspace created: {workspace.id} by user {current_user.id}")

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        description=workspace.description,
        owner_id=workspace.owner_id,
        is_public=workspace.is_public,
        allow_guest_edit=workspace.allow_guest_edit,
        allow_guest_view=workspace.allow_guest_view,
        tile_count=0,
        domain_count=0,
        member_count=1,
        created_at=workspace.created_at.isoformat()
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ワークスペース詳細を取得"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # アクセス権限チェック
    is_owner = workspace.owner_id == current_user.id
    is_member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == current_user.id
    ).first() is not None
    is_public = workspace.is_public

    if not (is_owner or is_member or is_public):
        raise HTTPException(status_code=403, detail="Access denied")

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        description=workspace.description,
        owner_id=workspace.owner_id,
        is_public=workspace.is_public,
        allow_guest_edit=workspace.allow_guest_edit,
        allow_guest_view=workspace.allow_guest_view,
        tile_count=workspace.tile_count,
        domain_count=workspace.domain_count,
        member_count=workspace.member_count,
        created_at=workspace.created_at.isoformat()
    )


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    workspace_data: WorkspaceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ワークスペースを更新"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # オーナーのみ更新可能
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only workspace owner can update settings")

    # 更新
    if workspace_data.name is not None:
        workspace.name = workspace_data.name
    if workspace_data.description is not None:
        workspace.description = workspace_data.description
    if workspace_data.is_public is not None:
        workspace.is_public = workspace_data.is_public
    if workspace_data.allow_guest_edit is not None:
        workspace.allow_guest_edit = workspace_data.allow_guest_edit
    if workspace_data.allow_guest_view is not None:
        workspace.allow_guest_view = workspace_data.allow_guest_view

    db.commit()
    db.refresh(workspace)

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        description=workspace.description,
        owner_id=workspace.owner_id,
        is_public=workspace.is_public,
        allow_guest_edit=workspace.allow_guest_edit,
        allow_guest_view=workspace.allow_guest_view,
        tile_count=workspace.tile_count,
        domain_count=workspace.domain_count,
        member_count=workspace.member_count,
        created_at=workspace.created_at.isoformat()
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ワークスペースを削除"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # オーナーのみ削除可能
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only workspace owner can delete")

    # DBファイルを削除
    if workspace.db_path and os.path.exists(workspace.db_path):
        try:
            os.remove(workspace.db_path)
        except Exception as e:
            logger.warning(f"Failed to delete workspace DB file: {e}")

    db.delete(workspace)
    db.commit()

    logger.info(f"Workspace deleted: {workspace_id} by user {current_user.id}")
    return None


# ===== メンバー管理 =====

@router.get("/{workspace_id}/members", response_model=List[WorkspaceMemberResponse])
async def list_members(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ワークスペースメンバー一覧を取得"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # アクセス権限チェック
    is_owner = workspace.owner_id == current_user.id
    is_member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == current_user.id
    ).first() is not None

    if not (is_owner or is_member):
        raise HTTPException(status_code=403, detail="Access denied")

    members = db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace_id).all()

    return [WorkspaceMemberResponse(
        id=member.id,
        user_id=member.user_id,
        username=member.user.username,
        display_name=member.user.display_name,
        role=member.role,
        can_read=member.can_read,
        can_write=member.can_write,
        can_delete=member.can_delete,
        joined_at=member.joined_at.isoformat()
    ) for member in members]
