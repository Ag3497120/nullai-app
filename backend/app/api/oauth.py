"""
完全なOAuth認証API - Google & ORCID
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from backend.app.database.session import get_db
from backend.app.services.oauth_service import OAuthService, get_oauth_service
from backend.app.utils.jwt_utils import create_access_token
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class AuthResponse(BaseModel):
    """認証レスポンス"""
    success: bool
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user_id: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    is_expert: bool = False
    provider: str
    message: str


class AuthStatusResponse(BaseModel):
    """認証ステータス"""
    google_available: bool
    orcid_available: bool
    guest_access_enabled: bool = True


# ===== ステータス確認 =====

@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(oauth_service: OAuthService = Depends(get_oauth_service)):
    """利用可能な認証方法を取得"""
    return AuthStatusResponse(
        google_available=bool(oauth_service.GOOGLE_CLIENT_ID),
        orcid_available=bool(oauth_service.ORCID_CLIENT_ID),
        guest_access_enabled=True
    )


# ===== Google OAuth =====

@router.get("/google/login")
async def google_login(
    redirect_url: Optional[str] = Query(None, description="認証後のリダイレクト先"),
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """Google OAuth認証を開始"""
    if not oauth_service.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google authentication is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )

    auth_url = oauth_service.get_google_auth_url(db, redirect_url)
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="OAuth state token"),
    error: Optional[str] = Query(None, description="OAuth error"),
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """Googleからのコールバック処理"""
    try:
        # エラーチェック
        if error:
            logger.error(f"Google OAuth error: {error}")
            raise HTTPException(status_code=400, detail=f"Google authentication failed: {error}")

        # stateを検証
        oauth_state = oauth_service.verify_state(db, state, "google")
        if not oauth_state:
            raise HTTPException(status_code=400, detail="Invalid or expired state token")

        # 認証コードをトークンに交換
        tokens = await oauth_service.exchange_google_code(code)

        # ユーザー情報を取得
        userinfo = await oauth_service.get_google_userinfo(tokens["access_token"])

        # ユーザーを作成または更新
        user = oauth_service.create_or_update_google_user(db, userinfo, tokens)

        # JWTトークンを発行
        access_token = create_access_token(data={
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "is_expert": user.is_expert
        })

        # OAuth stateを削除
        db.delete(oauth_state)
        db.commit()

        # リダイレクト先を決定
        redirect_url = oauth_state.redirect_url or "/"
        final_url = f"{redirect_url}?token={access_token}&provider=google"

        logger.info(f"Google OAuth successful for user {user.id}")
        return RedirectResponse(url=final_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


# ===== ORCID OAuth =====

@router.get("/orcid/login")
async def orcid_login(
    redirect_url: Optional[str] = Query(None, description="認証後のリダイレクト先"),
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """ORCID OAuth認証を開始"""
    if not oauth_service.ORCID_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="ORCID authentication is not configured. Set ORCID_CLIENT_ID and ORCID_CLIENT_SECRET."
        )

    auth_url = oauth_service.get_orcid_auth_url(db, redirect_url)
    return RedirectResponse(url=auth_url)


@router.get("/orcid/callback")
async def orcid_callback(
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="OAuth state token"),
    error: Optional[str] = Query(None, description="OAuth error"),
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """ORCIDからのコールバック処理"""
    try:
        # エラーチェック
        if error:
            logger.error(f"ORCID OAuth error: {error}")
            raise HTTPException(status_code=400, detail=f"ORCID authentication failed: {error}")

        # stateを検証
        oauth_state = oauth_service.verify_state(db, state, "orcid")
        if not oauth_state:
            raise HTTPException(status_code=400, detail="Invalid or expired state token")

        # 認証コードをトークンに交換
        tokens = await oauth_service.exchange_orcid_code(code)
        orcid_id = tokens.get("orcid")
        name = tokens.get("name")

        if not orcid_id:
            raise HTTPException(status_code=400, detail="Failed to obtain ORCID iD")

        # ユーザーを作成または更新
        orcid_data = {"orcid": orcid_id, "name": name}
        user = oauth_service.create_or_update_orcid_user(db, orcid_data, tokens)

        # JWTトークンを発行
        access_token = create_access_token(data={
            "sub": user.id,
            "orcid_id": user.orcid_id,
            "role": user.role,
            "is_expert": True
        })

        # OAuth stateを削除
        db.delete(oauth_state)
        db.commit()

        # リダイレクト先を決定
        redirect_url = oauth_state.redirect_url or "/"
        final_url = f"{redirect_url}?token={access_token}&provider=orcid&expert=true"

        logger.info(f"ORCID OAuth successful for expert user {user.id} (ORCID: {orcid_id})")
        return RedirectResponse(url=final_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ORCID OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


# ===== GitHub OAuth =====

@router.get("/github/login")
async def github_login(
    redirect_url: Optional[str] = Query(None, description="認証後のリダイレクト先"),
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """GitHub OAuth認証を開始"""
    if not oauth_service.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="GitHub authentication is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
        )
    auth_url = oauth_service.get_github_auth_url(db, redirect_url)
    return RedirectResponse(url=auth_url)


@router.get("/github/callback")
async def github_callback(
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="OAuth state token"),
    error: Optional[str] = Query(None, description="OAuth error"),
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """GitHubからのコールバック処理"""
    try:
        if error:
            logger.error(f"GitHub OAuth error: {error}")
            raise HTTPException(status_code=400, detail=f"GitHub authentication failed: {error}")

        oauth_state = oauth_service.verify_state(db, state, "github")
        if not oauth_state:
            raise HTTPException(status_code=400, detail="Invalid or expired state token")

        tokens = await oauth_service.exchange_github_code(code)
        if "access_token" not in tokens:
            raise HTTPException(status_code=400, detail=f"Failed to obtain access token from GitHub: {tokens.get('error_description')}")

        userinfo = await oauth_service.get_github_userinfo(tokens["access_token"])
        user = oauth_service.create_or_update_github_user(db, userinfo, tokens)

        access_token = create_access_token(data={
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "is_expert": user.is_expert,
        })

        db.delete(oauth_state)
        db.commit()

        redirect_url = oauth_state.redirect_url or "/"
        final_url = f"{redirect_url}?token={access_token}&provider=github"

        logger.info(f"GitHub OAuth successful for user {user.id}")
        return RedirectResponse(url=final_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


# ===== ゲストアクセス =====

@router.post("/guest", response_model=AuthResponse)
async def create_guest_session():
    """ゲストセッションを作成"""
    try:
        # ゲスト用のJWTトークンを発行
        import uuid
        guest_id = f"guest_{uuid.uuid4().hex[:12]}"

        access_token = create_access_token(data={
            "sub": guest_id,
            "role": "guest",
            "is_guest": True,
            "is_expert": False
        })

        logger.info(f"Guest session created: {guest_id}")

        return AuthResponse(
            success=True,
            access_token=access_token,
            token_type="bearer",
            user_id=guest_id,
            username="guest",
            display_name="Guest User",
            is_expert=False,
            provider="guest",
            message="Guest session created successfully"
        )

    except Exception as e:
        logger.error(f"Guest session creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create guest session: {str(e)}")

