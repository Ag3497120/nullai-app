"""
NullAI ORCID OAuth認証API

専門家認証のためのORCID OAuth2.0統合。
ORCID認証済みユーザーには「専門家」ステータスが付与される。
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import httpx
import os
from datetime import datetime, timedelta
import secrets

from backend.app.middleware.auth import get_current_user, get_user_or_guest, User, GuestUser
from backend.app.utils.jwt_utils import create_access_token

router = APIRouter()

# ORCID OAuth設定（環境変数から取得）
ORCID_CLIENT_ID = os.getenv("ORCID_CLIENT_ID", "")
ORCID_CLIENT_SECRET = os.getenv("ORCID_CLIENT_SECRET", "")
ORCID_REDIRECT_URI = os.getenv("ORCID_REDIRECT_URI", "http://localhost:8000/api/auth/orcid/callback")
ORCID_AUTH_URL = "https://orcid.org/oauth/authorize"
ORCID_TOKEN_URL = "https://orcid.org/oauth/token"
ORCID_API_URL = "https://pub.orcid.org/v3.0"

# サンドボックス環境用（開発時）
ORCID_SANDBOX = os.getenv("ORCID_SANDBOX", "false").lower() == "true"
if ORCID_SANDBOX:
    ORCID_AUTH_URL = "https://sandbox.orcid.org/oauth/authorize"
    ORCID_TOKEN_URL = "https://sandbox.orcid.org/oauth/token"
    ORCID_API_URL = "https://pub.sandbox.orcid.org/v3.0"

# 一時的なstateトークンを保存（本番環境ではRedis等を使用）
_oauth_states = {}


class OrcidProfile(BaseModel):
    """ORCIDプロフィール情報"""
    orcid_id: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    display_name: str
    affiliations: list = []
    verified_at: datetime


class OrcidLinkRequest(BaseModel):
    """ORCID連携リクエスト"""
    redirect_url: Optional[str] = None


class OrcidVerifyResponse(BaseModel):
    """ORCID認証レスポンス"""
    success: bool
    orcid_id: Optional[str] = None
    display_name: Optional[str] = None
    is_expert: bool = False
    access_token: Optional[str] = None
    message: str


@router.get("/orcid/status")
async def get_orcid_status(
    current_user: User = Depends(get_user_or_guest)
):
    """
    現在のユーザーのORCID認証状態を取得。
    ゲストユーザーも利用可能。
    """
    if isinstance(current_user, GuestUser):
        return {
            "is_authenticated": False,
            "is_expert": False,
            "orcid_id": None,
            "orcid_available": bool(ORCID_CLIENT_ID)
        }

    return {
        "is_authenticated": True,
        "is_expert": current_user.is_expert,
        "orcid_id": current_user.orcid_id,
        "orcid_available": bool(ORCID_CLIENT_ID)
    }


@router.get("/orcid/authorize")
async def authorize_orcid(
    redirect_url: Optional[str] = Query(None, description="認証後のリダイレクト先")
):
    """
    ORCID OAuth認証を開始。
    ユーザーをORCIDの認証ページにリダイレクトする。
    """
    if not ORCID_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="ORCID authentication is not configured. Set ORCID_CLIENT_ID environment variable."
        )

    # CSRF対策用のstateトークンを生成
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "created_at": datetime.utcnow(),
        "redirect_url": redirect_url or "http://localhost:5173"
    }

    # 古いstateトークンをクリーンアップ（10分以上前のもの）
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    expired_states = [k for k, v in _oauth_states.items() if v["created_at"] < cutoff]
    for k in expired_states:
        del _oauth_states[k]

    # ORCID認証URLを構築
    auth_url = (
        f"{ORCID_AUTH_URL}"
        f"?client_id={ORCID_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=/authenticate"
        f"&redirect_uri={ORCID_REDIRECT_URI}"
        f"&state={state}"
    )

    return {"authorization_url": auth_url, "state": state}


@router.get("/orcid/callback")
async def orcid_callback(
    code: str = Query(..., description="ORCID認証コード"),
    state: str = Query(..., description="CSRFトークン")
):
    """
    ORCID OAuth認証コールバック。
    認証コードをアクセストークンに交換し、ユーザー情報を取得する。
    """
    # stateトークンの検証
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    state_data = _oauth_states.pop(state)
    redirect_url = state_data.get("redirect_url", "http://localhost:5173")

    if not ORCID_CLIENT_ID or not ORCID_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="ORCID authentication is not configured")

    # 認証コードをアクセストークンに交換
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            ORCID_TOKEN_URL,
            data={
                "client_id": ORCID_CLIENT_ID,
                "client_secret": ORCID_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": ORCID_REDIRECT_URI
            },
            headers={"Accept": "application/json"}
        )

        if token_response.status_code != 200:
            error_detail = token_response.json() if token_response.headers.get("content-type", "").startswith("application/json") else token_response.text
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code for token: {error_detail}"
            )

        token_data = token_response.json()
        orcid_id = token_data.get("orcid")
        orcid_access_token = token_data.get("access_token")

        if not orcid_id:
            raise HTTPException(status_code=400, detail="ORCID ID not found in response")

        # ORCIDプロフィール情報を取得
        profile_response = await client.get(
            f"{ORCID_API_URL}/{orcid_id}/person",
            headers={
                "Authorization": f"Bearer {orcid_access_token}",
                "Accept": "application/json"
            }
        )

        display_name = orcid_id
        given_name = None
        family_name = None

        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            name_data = profile_data.get("name", {})
            given_name = name_data.get("given-names", {}).get("value")
            family_name = name_data.get("family-name", {}).get("value")

            if given_name and family_name:
                display_name = f"{given_name} {family_name}"
            elif given_name:
                display_name = given_name

    # JWTトークンを生成（専門家ステータス付き）
    access_token = create_access_token(
        data={
            "sub": f"orcid:{orcid_id}",
            "role": "expert",
            "is_expert": True,
            "orcid_id": orcid_id,
            "display_name": display_name
        }
    )

    # フロントエンドにリダイレクト（トークン付き）
    redirect_with_token = f"{redirect_url}?orcid_token={access_token}&orcid_id={orcid_id}&display_name={display_name}"
    return RedirectResponse(url=redirect_with_token)


@router.post("/orcid/verify", response_model=OrcidVerifyResponse)
async def verify_orcid_token(
    orcid_access_token: str,
    current_user: User = Depends(get_user_or_guest)
):
    """
    既存のORCIDアクセストークンを検証し、専門家ステータスを付与。
    既存アカウントにORCIDを連携する場合に使用。
    """
    if not orcid_access_token:
        return OrcidVerifyResponse(
            success=False,
            message="ORCID access token is required"
        )

    async with httpx.AsyncClient() as client:
        # トークンの有効性を確認
        response = await client.get(
            f"{ORCID_API_URL}/me",
            headers={
                "Authorization": f"Bearer {orcid_access_token}",
                "Accept": "application/json"
            }
        )

        if response.status_code != 200:
            return OrcidVerifyResponse(
                success=False,
                message="Invalid or expired ORCID access token"
            )

        orcid_data = response.json()
        orcid_id = orcid_data.get("orcid-identifier", {}).get("path")

        if not orcid_id:
            return OrcidVerifyResponse(
                success=False,
                message="Could not retrieve ORCID ID"
            )

        # プロフィール情報を取得
        profile_response = await client.get(
            f"{ORCID_API_URL}/{orcid_id}/person",
            headers={
                "Authorization": f"Bearer {orcid_access_token}",
                "Accept": "application/json"
            }
        )

        display_name = orcid_id
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            name_data = profile_data.get("name", {})
            given_name = name_data.get("given-names", {}).get("value", "")
            family_name = name_data.get("family-name", {}).get("value", "")
            if given_name and family_name:
                display_name = f"{given_name} {family_name}"
            elif given_name:
                display_name = given_name

    # 新しいJWTトークンを生成
    user_id = current_user.id if not isinstance(current_user, GuestUser) else f"orcid:{orcid_id}"
    access_token = create_access_token(
        data={
            "sub": user_id,
            "role": "expert",
            "is_expert": True,
            "orcid_id": orcid_id,
            "display_name": display_name
        }
    )

    return OrcidVerifyResponse(
        success=True,
        orcid_id=orcid_id,
        display_name=display_name,
        is_expert=True,
        access_token=access_token,
        message="ORCID verification successful. Expert status granted."
    )


@router.get("/orcid/profile/{orcid_id}")
async def get_orcid_profile(
    orcid_id: str,
    current_user: User = Depends(get_user_or_guest)
):
    """
    公開ORCIDプロフィールを取得。
    専門家の認証情報を表示するために使用。
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ORCID_API_URL}/{orcid_id}/person",
            headers={"Accept": "application/json"}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=404, detail=f"ORCID profile not found: {orcid_id}")

        profile_data = response.json()
        name_data = profile_data.get("name", {})

        given_name = name_data.get("given-names", {}).get("value")
        family_name = name_data.get("family-name", {}).get("value")
        display_name = orcid_id

        if given_name and family_name:
            display_name = f"{given_name} {family_name}"
        elif given_name:
            display_name = given_name

        # 所属情報を取得
        affiliations_response = await client.get(
            f"{ORCID_API_URL}/{orcid_id}/employments",
            headers={"Accept": "application/json"}
        )

        affiliations = []
        if affiliations_response.status_code == 200:
            affiliations_data = affiliations_response.json()
            for group in affiliations_data.get("affiliation-group", []):
                for summary in group.get("summaries", []):
                    emp = summary.get("employment-summary", {})
                    org = emp.get("organization", {})
                    affiliations.append({
                        "organization": org.get("name"),
                        "role": emp.get("role-title"),
                        "department": emp.get("department-name")
                    })

        return {
            "orcid_id": orcid_id,
            "orcid_url": f"https://orcid.org/{orcid_id}",
            "display_name": display_name,
            "given_name": given_name,
            "family_name": family_name,
            "affiliations": affiliations[:5],  # 最大5件
            "is_verified": True
        }
