from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.config import settings

# --- データベース接続設定 ---
# SQLiteを使用する場合
# SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, echo=True
# )

# PostgreSQLなどを使用する場合
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    リクエストごとにDBセッションを提供する依存性注入関数
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
