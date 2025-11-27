from sqlalchemy.orm import Session
from backend.app.database.models import User
from backend.app.schemas.auth import UserCreate
from backend.app.utils.password_hash import get_password_hash, verify_password
from backend.app.utils.jwt_utils import create_access_token

class AuthService:
    def get_user_by_email(self, db: Session, email: str) -> User | None:
        """メールアドレスでユーザーを検索する"""
        return db.query(User).filter(User.email == email).first()

    def create_user(self, db: Session, user: UserCreate) -> User:
        """新規ユーザーを作成する"""
        hashed_password = get_password_hash(user.password)
        db_user = User(email=user.email, hashed_password=hashed_password)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    def authenticate_user(self, db: Session, email: str, password: str) -> User | None:
        """ユーザーを認証する"""
        user = self.get_user_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

# --- 依存性注入用の関数 ---
def get_auth_service() -> AuthService:
    return AuthService()
