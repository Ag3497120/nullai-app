#!/usr/bin/env python3
"""テストユーザーを作成"""
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from backend.app.database.session import SessionLocal
from backend.app.database.models import User
from backend.app.utils.password_hash import get_password_hash

def create_test_user():
    """テストユーザーを作成"""
    db = SessionLocal()

    try:
        # 既存ユーザーを確認
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        if existing_user:
            print("✅ テストユーザーは既に存在します")
            print(f"   Email: test@example.com")
            print(f"   Password: test123")
            print(f"   Role: {existing_user.role}")
            return

        # テストユーザーを作成
        test_user = User(
            email="test@example.com",
            username="testuser",
            hashed_password=get_password_hash("test123"),
            role="editor",  # editorロールで作成
            is_active=True
        )

        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        print("✅ テストユーザーを作成しました！")
        print(f"   Email: test@example.com")
        print(f"   Password: test123")
        print(f"   Role: editor")
        print()
        print("フロントエンド (http://localhost:5173) でログインできます")

    except Exception as e:
        print(f"❌ エラー: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user()
