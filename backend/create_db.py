import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database.session import engine
from backend.app.database.models import Base, User # Userモデルをインポート

def create_database():
    print("データベースにテーブルを作成しています...")
    # すべてのテーブルを作成
    Base.metadata.create_all(bind=engine)
    print("テーブルの作成が完了しました。")

if __name__ == "__main__":
    create_database()
