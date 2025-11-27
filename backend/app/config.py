from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """アプリケーション設定を管理するクラス"""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # データベース設定
    DATABASE_URL: str = "sqlite:///./sql_app.db" # デフォルトはSQLite
    
    # Redis設定
    REDIS_URL: str = "redis://localhost:6379"

    # JWT認証設定
    SECRET_KEY: str = "super-secret-key" # 本番環境では強力なキーに変更すること
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # アクセストークンの有効期限 (分)

    # CORS設定
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"] # フロントエンドのURL

    # デバッグモード
    DEBUG: bool = False

    # 推論エンジンとDBの設定 (環境変数から読み込む)
    DEEPSEEK_API_URL: str = "http://host.docker.internal:11434"
    DEEPSEEK_MODEL_NAME: str = "deepseek-r1:32b"
    DB_PATH: str = "ilm_athens_medical_db.iath"

settings = Settings()
