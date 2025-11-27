from fastapi import Request, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from backend.app.utils.jwt_utils import verify_token
from backend.app.schemas.auth import TokenData


@dataclass
class User:
    """認証済みユーザー"""
    id: str
    email: str = ""
    role: str = "viewer"  # guest, viewer, editor, expert, admin
    is_expert: bool = False
    orcid_id: Optional[str] = None
    verified_at: Optional[datetime] = None
    display_name: str = ""


@dataclass
class GuestUser:
    """ゲストユーザー（未認証）"""
    id: str = "guest"
    role: str = "guest"
    is_expert: bool = False
    orcid_id: Optional[str] = None


# OAuth2スキーム（トークン取得エンドポイント）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    JWTトークンを検証し、現在のユーザーを取得する。

    Raises:
        HTTPException: トークンが無効または期限切れの場合
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception

    return User(
        id=token_data.user_id,
        role=token_data.role or "viewer",
        is_expert=token_data.is_expert,
        orcid_id=token_data.orcid_id,
        display_name=token_data.display_name or ""
    )


async def get_current_user_optional(
    token: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False))
) -> Optional[User]:
    """
    オプショナルなユーザー認証。トークンがない場合はNoneを返す。
    認証が任意のエンドポイント用。
    """
    if token is None:
        return None

    token_data = verify_token(token)
    if token_data is None:
        return None

    return User(
        id=token_data.user_id,
        role=token_data.role or "viewer",
        is_expert=token_data.is_expert,
        orcid_id=token_data.orcid_id,
        display_name=token_data.display_name or ""
    )


async def get_user_or_guest(
    token: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False))
) -> User:
    """
    ゲストアクセスを許可するエンドポイント用。
    認証済みの場合はUserを返し、未認証の場合はGuestUserを返す。
    """
    if token is None:
        return GuestUser()

    token_data = verify_token(token)
    if token_data is None:
        return GuestUser()

    return User(
        id=token_data.user_id,
        role=token_data.role or "viewer",
        is_expert=token_data.is_expert,
        orcid_id=token_data.orcid_id,
        display_name=token_data.display_name or ""
    )


def require_role(required_role: str):
    """
    特定のロールを必要とする依存性デコレータ。

    使用例:
        @router.post("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role("admin"))):
            ...
    """
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return user
    return role_checker


def require_expert():
    """
    ORCID認証済み専門家を必要とする依存性デコレータ。
    """
    async def expert_checker(user: User = Depends(get_current_user)) -> User:
        if not user.is_expert or not user.orcid_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ORCID-verified expert status required"
            )
        return user
    return expert_checker


def require_authenticated():
    """
    ゲストを除外し、認証済みユーザーのみを許可する依存性デコレータ。
    """
    async def auth_checker(user: User = Depends(get_user_or_guest)) -> User:
        if isinstance(user, GuestUser) or user.role == "guest":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        return user
    return auth_checker


class JWTMiddleware:
    """
    JWT認証ミドルウェア（オプショナル - 依存性注入推奨）
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope)
            # Authorization ヘッダーからトークンを取得
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                token_data = verify_token(token)
                if token_data:
                    # requestのstateにユーザー情報を格納
                    scope["state"] = scope.get("state", {})
                    scope["state"]["user"] = User(
                        id=token_data.user_id,
                        role=token_data.role or "viewer"
                    )

        await self.app(scope, receive, send)