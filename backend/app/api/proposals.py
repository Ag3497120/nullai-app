"""
編集提案・検証ワークフローAPI（専門家認証対応版）

知識タイルの編集提案の作成、レビュー、承認/却下を管理する。
ORCID認証済み専門家による編集には認証マークが付与される。
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import json
import os
import uuid

from backend.app.middleware.auth import (
    get_current_user, get_user_or_guest, require_role,
    require_expert, User, GuestUser
)

router = APIRouter()

PROPOSALS_PATH = "proposals.json"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProposalType(str, Enum):
    CREATE = "create"       # 新規タイル作成
    UPDATE = "update"       # 既存タイル更新
    DELETE = "delete"       # タイル削除
    MERGE = "merge"         # タイル統合


class VerificationMark(BaseModel):
    """専門家認証マーク"""
    is_expert_verified: bool = False
    expert_orcid_id: Optional[str] = None
    expert_name: Optional[str] = None
    verification_date: Optional[str] = None
    verification_type: str = "none"  # none, community, expert, multi_expert


class ProposalCreate(BaseModel):
    """編集提案の作成リクエスト"""
    proposal_type: ProposalType
    domain_id: str
    tile_id: Optional[str] = None  # 更新/削除の場合は必須
    title: str
    description: str
    proposed_content: Optional[Dict[str, Any]] = None
    proposed_coordinates: Optional[List[float]] = None
    justification: str  # 変更理由


class ProposalReview(BaseModel):
    """レビュー結果"""
    status: ProposalStatus
    reviewer_comment: str
    validation_score: Optional[float] = None


class ProposalResponse(BaseModel):
    """提案レスポンス"""
    proposal_id: str
    proposal_type: str
    domain_id: str
    tile_id: Optional[str]
    title: str
    description: str
    proposed_content: Optional[Dict[str, Any]]
    proposed_coordinates: Optional[List[float]]
    justification: str
    status: str
    created_by: str
    created_at: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_comment: Optional[str] = None
    validation_score: Optional[float] = None
    # 認証マーク関連
    creator_is_expert: bool = False
    creator_orcid_id: Optional[str] = None
    creator_display_name: Optional[str] = None
    reviewer_is_expert: bool = False
    reviewer_orcid_id: Optional[str] = None
    reviewer_display_name: Optional[str] = None
    verification_mark: Optional[VerificationMark] = None


def load_proposals() -> Dict:
    """提案データを読み込む"""
    if os.path.exists(PROPOSALS_PATH):
        with open(PROPOSALS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"proposals": []}


def save_proposals(data: Dict):
    """提案データを保存"""
    with open(PROPOSALS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _calculate_verification_mark(proposal: Dict) -> VerificationMark:
    """提案の認証マークを計算する"""
    creator_is_expert = proposal.get("creator_is_expert", False)
    reviewer_is_expert = proposal.get("reviewer_is_expert", False)

    if creator_is_expert and reviewer_is_expert:
        return VerificationMark(
            is_expert_verified=True,
            expert_orcid_id=proposal.get("reviewer_orcid_id"),
            expert_name=proposal.get("reviewer_display_name"),
            verification_date=proposal.get("reviewed_at"),
            verification_type="multi_expert"
        )
    elif reviewer_is_expert:
        return VerificationMark(
            is_expert_verified=True,
            expert_orcid_id=proposal.get("reviewer_orcid_id"),
            expert_name=proposal.get("reviewer_display_name"),
            verification_date=proposal.get("reviewed_at"),
            verification_type="expert"
        )
    elif creator_is_expert:
        return VerificationMark(
            is_expert_verified=True,
            expert_orcid_id=proposal.get("creator_orcid_id"),
            expert_name=proposal.get("creator_display_name"),
            verification_date=proposal.get("created_at"),
            verification_type="expert"
        )
    elif proposal.get("status") == ProposalStatus.APPROVED.value:
        return VerificationMark(
            is_expert_verified=False,
            verification_type="community"
        )
    else:
        return VerificationMark(
            is_expert_verified=False,
            verification_type="none"
        )


@router.post("/", response_model=ProposalResponse)
async def create_proposal(
    proposal: ProposalCreate,
    current_user: User = Depends(get_current_user)
):
    """
    編集提案を作成する。
    すべての認証済みユーザーが提案可能。
    ORCID認証済み専門家の場合は認証マークが付与される。
    """
    data = load_proposals()

    # 専門家情報を取得
    is_expert = getattr(current_user, 'is_expert', False)
    orcid_id = getattr(current_user, 'orcid_id', None)
    display_name = getattr(current_user, 'display_name', None)

    new_proposal = {
        "proposal_id": str(uuid.uuid4()),
        "proposal_type": proposal.proposal_type.value,
        "domain_id": proposal.domain_id,
        "tile_id": proposal.tile_id,
        "title": proposal.title,
        "description": proposal.description,
        "proposed_content": proposal.proposed_content,
        "proposed_coordinates": proposal.proposed_coordinates,
        "justification": proposal.justification,
        "status": ProposalStatus.PENDING.value,
        "created_by": current_user.id,
        "created_at": datetime.utcnow().isoformat(),
        "reviewed_by": None,
        "reviewed_at": None,
        "reviewer_comment": None,
        "validation_score": None,
        # 専門家認証情報
        "creator_is_expert": is_expert,
        "creator_orcid_id": orcid_id,
        "creator_display_name": display_name,
        "reviewer_is_expert": False,
        "reviewer_orcid_id": None,
        "reviewer_display_name": None
    }

    # 認証マークを計算
    verification_mark = _calculate_verification_mark(new_proposal)
    new_proposal["verification_mark"] = verification_mark.dict()

    data["proposals"].append(new_proposal)
    save_proposals(data)

    return ProposalResponse(**new_proposal, verification_mark=verification_mark)


@router.get("/", response_model=List[ProposalResponse])
async def list_proposals(
    status: Optional[str] = None,
    domain_id: Optional[str] = None,
    current_user: User = Depends(get_user_or_guest)
):
    """
    提案一覧を取得する（ゲストアクセス可）。
    フィルタリング可能（status, domain_id）。
    """
    data = load_proposals()
    proposals = data.get("proposals", [])

    # フィルタリング
    if status:
        proposals = [p for p in proposals if p["status"] == status]
    if domain_id:
        proposals = [p for p in proposals if p["domain_id"] == domain_id]

    # 新しい順にソート
    proposals.sort(key=lambda x: x["created_at"], reverse=True)

    # 認証マークを再計算
    result = []
    for p in proposals:
        verification_mark = _calculate_verification_mark(p)
        result.append(ProposalResponse(**p, verification_mark=verification_mark))

    return result


@router.get("/my", response_model=List[ProposalResponse])
async def list_my_proposals(
    current_user: User = Depends(get_current_user)
):
    """
    自分が作成した提案一覧を取得する。
    """
    data = load_proposals()
    proposals = [
        p for p in data.get("proposals", [])
        if p["created_by"] == current_user.id
    ]

    proposals.sort(key=lambda x: x["created_at"], reverse=True)
    return [ProposalResponse(**p) for p in proposals]


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: str,
    current_user: User = Depends(get_user_or_guest)
):
    """
    特定の提案を取得する（ゲストアクセス可）。
    """
    data = load_proposals()

    for p in data.get("proposals", []):
        if p["proposal_id"] == proposal_id:
            verification_mark = _calculate_verification_mark(p)
            return ProposalResponse(**p, verification_mark=verification_mark)

    raise HTTPException(status_code=404, detail="Proposal not found")


@router.put("/{proposal_id}/review")
async def review_proposal(
    proposal_id: str,
    review: ProposalReview,
    current_user: User = Depends(require_role("editor"))
):
    """
    提案をレビューする（承認/却下）。
    editorまたはadminロールが必要。
    ORCID認証済み専門家がレビューした場合は認証マークが付与される。
    """
    data = load_proposals()

    # レビュアーの専門家情報を取得
    reviewer_is_expert = getattr(current_user, 'is_expert', False)
    reviewer_orcid_id = getattr(current_user, 'orcid_id', None)
    reviewer_display_name = getattr(current_user, 'display_name', None)

    for i, p in enumerate(data.get("proposals", [])):
        if p["proposal_id"] == proposal_id:
            # 自分の提案は自分でレビューできない
            if p["created_by"] == current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Cannot review your own proposal"
                )

            data["proposals"][i].update({
                "status": review.status.value,
                "reviewed_by": current_user.id,
                "reviewed_at": datetime.utcnow().isoformat(),
                "reviewer_comment": review.reviewer_comment,
                "validation_score": review.validation_score,
                # 専門家認証情報
                "reviewer_is_expert": reviewer_is_expert,
                "reviewer_orcid_id": reviewer_orcid_id,
                "reviewer_display_name": reviewer_display_name
            })

            # 認証マークを再計算
            verification_mark = _calculate_verification_mark(data["proposals"][i])
            data["proposals"][i]["verification_mark"] = verification_mark.dict()

            save_proposals(data)

            # 承認された場合、実際の変更を適用
            if review.status == ProposalStatus.APPROVED:
                await _apply_proposal(data["proposals"][i])

            return {
                "message": f"Proposal {review.status.value}",
                "proposal_id": proposal_id,
                "reviewed_by": current_user.id,
                "reviewer_is_expert": reviewer_is_expert,
                "verification_mark": verification_mark.dict()
            }

    raise HTTPException(status_code=404, detail="Proposal not found")


@router.delete("/{proposal_id}")
async def delete_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    自分の提案を削除する（pending状態のみ）。
    """
    data = load_proposals()

    for i, p in enumerate(data.get("proposals", [])):
        if p["proposal_id"] == proposal_id:
            # 自分の提案のみ削除可能
            if p["created_by"] != current_user.id and current_user.role != "admin":
                raise HTTPException(
                    status_code=403,
                    detail="Can only delete your own proposals"
                )

            # pending状態のみ削除可能
            if p["status"] != ProposalStatus.PENDING.value:
                raise HTTPException(
                    status_code=400,
                    detail="Can only delete pending proposals"
                )

            del data["proposals"][i]
            save_proposals(data)

            return {"message": "Proposal deleted", "proposal_id": proposal_id}

    raise HTTPException(status_code=404, detail="Proposal not found")


async def _apply_proposal(proposal: Dict):
    """
    承認された提案を実際に適用する。
    （IathDB統合時に実装）
    """
    proposal_type = proposal["proposal_type"]

    if proposal_type == ProposalType.CREATE.value:
        # 新規タイル作成
        print(f"Creating new tile in domain {proposal['domain_id']}")
        # TODO: IathDBに新規タイルを作成
        pass

    elif proposal_type == ProposalType.UPDATE.value:
        # タイル更新
        print(f"Updating tile {proposal['tile_id']}")
        # TODO: IathDBのタイルを更新
        pass

    elif proposal_type == ProposalType.DELETE.value:
        # タイル削除
        print(f"Deleting tile {proposal['tile_id']}")
        # TODO: IathDBからタイルを削除
        pass
