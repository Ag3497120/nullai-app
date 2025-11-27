"""
データベース初期化スクリプト
新しい認証システムとワークスペース機能のテーブルを作成します
"""
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from backend.app.database.models import Base
from backend.app.config import settings

def init_database():
    """データベーステーブルを作成"""
    print("Initializing database...")
    
    # データベースURLを取得
    database_url = settings.DATABASE_URL or "sqlite:///./sql_app.db"
    print(f"Database URL: {database_url}")
    
    # エンジンを作成
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    
    # 全テーブルを作成
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    print("✓ Database initialized successfully!")
    print("\nCreated tables:")
    for table in Base.metadata.tables.keys():
        print(f"  - {table}")
    
    print("\nYou can now start the application with:")
    print("  python -m uvicorn backend.app.main:app --reload")

if __name__ == "__main__":
    init_database()
