"""
OAuth認証サービス - Google & ORCID
"""
from typing import Optional, Dict, Any
import httpx
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.app.database.models import User, OAuthState, Workspace
from backend.app.utils.jwt_utils import create_access_token
import os


class OAuthService:
    """OAuth認証の共通サービスクラス"""

    # Google OAuth設定
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    # ORCID OAuth設定
    ORCID_CLIENT_ID = os.getenv("ORCID_CLIENT_ID", "")
    ORCID_CLIENT_SECRET = os.getenv("ORCID_CLIENT_SECRET", "")
    ORCID_REDIRECT_URI = os.getenv("ORCID_REDIRECT_URI", "http://localhost:8000/api/auth/orcid/callback")
    ORCID_SANDBOX = os.getenv("ORCID_SANDBOX", "false").lower() == "true"

    # ORCID URLs
    ORCID_AUTH_URL = "https://sandbox.orcid.org/oauth/authorize" if ORCID_SANDBOX else "https://orcid.org/oauth/authorize"
    ORCID_TOKEN_URL = "https://sandbox.orcid.org/oauth/token" if ORCID_SANDBOX else "https://orcid.org/oauth/token"
    # ORCID API URL
    ORCID_API_URL = "https://pub.sandbox.orcid.org/v3.0" if ORCID_SANDBOX else "https://pub.orcid.org/v3.0"

    # GitHub OAuth設定
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
    GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/api/oauth/github/callback")
    GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
    GITHUB_USER_API_URL = "https://api.github.com/user"


    @staticmethod
    def generate_state(db: Session, provider: str, redirect_url: Optional[str] = None) -> str:
        """OAuth stateトークンを生成してDBに保存"""
        state = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        oauth_state = OAuthState(
            state=state,
            provider=provider,
            redirect_url=redirect_url,
            expires_at=expires_at
        )
        db.add(oauth_state)
        db.commit()
        return state

    @staticmethod
    def verify_state(db: Session, state: str, provider: str) -> Optional[OAuthState]:
        """stateトークンを検証"""
        oauth_state = db.query(OAuthState).filter(
            OAuthState.state == state,
            OAuthState.provider == provider
        ).first()

        if not oauth_state:
            return None

        if oauth_state.is_expired():
            db.delete(oauth_state)
            db.commit()
            return None

        return oauth_state

    @staticmethod
    def create_default_workspace(db: Session, user: User) -> Workspace:
        """ユーザーのデフォルトワークスペースを作成"""
        workspace = Workspace(
            name=f"{user.display_name or user.email}'s Workspace",
            slug=f"user-{user.id[:8]}",
            description="My personal knowledge workspace",
            owner_id=user.id,
            is_public=False,
            allow_guest_edit=True,
            allow_guest_view=True,
            db_type="sqlite",
            db_path=f"workspaces/user_{user.id}.db"
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace

    # ===== Google OAuth =====

    def get_google_auth_url(self, db: Session, redirect_url: Optional[str] = None) -> str:
        """Google OAuth認証URLを生成"""
        state = self.generate_state(db, "google", redirect_url)

        params = {
            "client_id": self.GOOGLE_CLIENT_ID,
            "redirect_uri": self.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.GOOGLE_AUTH_URL}?{query_string}"

    async def exchange_google_code(self, code: str) -> Dict[str, Any]:
        """Google認証コードをトークンに交換"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.GOOGLE_CLIENT_ID,
                    "client_secret": self.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": self.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return response.json()

    async def get_google_userinfo(self, access_token: str) -> Dict[str, Any]:
        """Googleユーザー情報を取得"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()

    def create_or_update_google_user(self, db: Session, userinfo: Dict[str, Any], tokens: Dict[str, Any]) -> User:
        """Googleユーザー情報からユーザーを作成または更新"""
        google_id = userinfo["id"]
        email = userinfo.get("email")

        # 既存ユーザーを検索
        user = db.query(User).filter(User.google_id == google_id).first()

        if not user and email:
            # メールアドレスで検索（既存アカウントとの連携）
            user = db.query(User).filter(User.email == email).first()

        if user:
            # 既存ユーザーを更新
            user.google_id = google_id
            user.email = email or user.email
            user.display_name = userinfo.get("name", user.display_name)
            user.avatar_url = userinfo.get("picture", user.avatar_url)
            user.google_access_token = tokens["access_token"]
            user.google_refresh_token = tokens.get("refresh_token", user.google_refresh_token)
            user.last_login_at = datetime.utcnow()
            user.auth_provider = "google"
        else:
            # 新規ユーザーを作成
            user = User(
                email=email,
                username=email.split("@")[0] if email else f"google_{google_id[:8]}",
                display_name=userinfo.get("name"),
                avatar_url=userinfo.get("picture"),
                auth_provider="google",
                google_id=google_id,
                google_access_token=tokens["access_token"],
                google_refresh_token=tokens.get("refresh_token"),
                role="viewer",
                is_guest=False,
                last_login_at=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # デフォルトワークスペースを作成
            self.create_default_workspace(db, user)

        db.commit()
        db.refresh(user)
        return user

    # ===== ORCID OAuth =====

    def get_orcid_auth_url(self, db: Session, redirect_url: Optional[str] = None) -> str:
        """ORCID OAuth認証URLを生成"""
        state = self.generate_state(db, "orcid", redirect_url)

        params = {
            "client_id": self.ORCID_CLIENT_ID,
            "response_type": "code",
            "scope": "/authenticate",
            "redirect_uri": self.ORCID_REDIRECT_URI,
            "state": state
        }

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.ORCID_AUTH_URL}?{query_string}"

    async def exchange_orcid_code(self, code: str) -> Dict[str, Any]:
        """ORCID認証コードをトークンに交換"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.ORCID_TOKEN_URL,
                data={
                    "client_id": self.ORCID_CLIENT_ID,
                    "client_secret": self.ORCID_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.ORCID_REDIRECT_URI
                },
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            return response.json()

    async def get_orcid_record(self, orcid_id: str, access_token: str) -> Dict[str, Any]:
        """ORCID公開レコードを取得"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.ORCID_API_URL}/{orcid_id}/record",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
            )
            response.raise_for_status()
            return response.json()

    def create_or_update_orcid_user(self, db: Session, orcid_data: Dict[str, Any], tokens: Dict[str, Any]) -> User:
        """ORCIDユーザー情報からユーザーを作成または更新"""
        orcid_id = orcid_data["orcid"]
        name = orcid_data.get("name")

        # 既存ユーザーを検索
        user = db.query(User).filter(User.orcid_id == orcid_id).first()

        if user:
            # 既存ユーザーを更新
            user.orcid_access_token = tokens["access_token"]
            user.orcid_refresh_token = tokens.get("refresh_token", user.orcid_refresh_token)
            user.is_expert = True
            user.expert_verification_status = "approved"
            user.last_login_at = datetime.utcnow()
            user.auth_provider = "orcid"
        else:
            # 新規ユーザーを作成
            user = User(
                username=f"orcid_{orcid_id.replace('-', '_')}",
                display_name=name or f"ORCID {orcid_id}",
                auth_provider="orcid",
                orcid_id=orcid_id,
                orcid_access_token=tokens["access_token"],
                orcid_refresh_token=tokens.get("refresh_token"),
                role="expert",
                is_expert=True,
                is_guest=False,
                expert_verification_status="approved",
                expert_credentials={"orcid_id": orcid_id, "verified_at": datetime.utcnow().isoformat()},
                last_login_at=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # デフォルトワークスペースを作成
            self.create_default_workspace(db, user)

        db.commit()
        db.refresh(user)
        return user

    # ===== GitHub OAuth =====

    def get_github_auth_url(self, db: Session, redirect_url: Optional[str] = None) -> str:
        """GitHub OAuth認証URLを生成"""
        state = self.generate_state(db, "github", redirect_url)
        params = {
            "client_id": self.GITHUB_CLIENT_ID,
            "redirect_uri": self.GITHUB_REDIRECT_URI,
            "scope": "read:user user:email",
            "state": state,
        }
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.GITHUB_AUTH_URL}?{query_string}"

    async def exchange_github_code(self, code: str) -> Dict[str, Any]:
        """GitHub認証コードをトークンに交換"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.GITHUB_TOKEN_URL,
                params={
                    "client_id": self.GITHUB_CLIENT_ID,
                    "client_secret": self.GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            return response.json()

    async def get_github_userinfo(self, access_token: str) -> Dict[str, Any]:
        """GitHubユーザー情報を取得"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GITHUB_USER_API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            response.raise_for_status()
            user_data = response.json()

            # 非公開メールアドレスを取得
            if not user_data.get("email"):
                emails_response = await client.get(
                    f"{self.GITHUB_USER_API_URL}/emails",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    primary_email = next((e['email'] for e in emails if e['primary'] and e['verified']), None)
                    if primary_email:
                        user_data['email'] = primary_email
            return user_data

    def create_or_update_github_user(self, db: Session, userinfo: Dict[str, Any], tokens: Dict[str, Any]) -> User:
        """GitHubユーザー情報からユーザーを作成または更新"""
        github_id = userinfo["id"]
        email = userinfo.get("email")
        
        user = db.query(User).filter(User.github_id == github_id).first()

        if not user and email:
            user = db.query(User).filter(User.email == email).first()

        if user:
            user.github_id = github_id
            user.email = email or user.email
            user.display_name = userinfo.get("name") or user.display_name
            user.avatar_url = userinfo.get("avatar_url", user.avatar_url)
            user.github_access_token = tokens["access_token"]
            user.last_login_at = datetime.utcnow()
            user.auth_provider = "github"
        else:
            user = User(
                email=email,
                username=userinfo.get("login", f"github_{github_id}"),
                display_name=userinfo.get("name"),
                avatar_url=userinfo.get("avatar_url"),
                auth_provider="github",
                github_id=github_id,
                github_access_token=tokens["access_token"],
                role="viewer",
                is_guest=False,
                last_login_at=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            self.create_default_workspace(db, user)

        db.commit()
        db.refresh(user)
        return user


def get_oauth_service() -> OAuthService:
    """依存性注入用"""
    return OAuthService()

