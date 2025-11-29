import os
import json
import logging
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging for this module
logger = logging.getLogger(__name__)

class ModelProvider(str, Enum):
    """モデルプロバイダーの種類"""
    HUGGINGFACE = "huggingface"
    HUGGINGFACE_API = "huggingface_api"
    MLX = "mlx"
    GGUF = "gguf"
    OLLAMA = "ollama"

class ModelConfig(BaseModel):
    """単一のモデル設定を表すPydanticモデル"""
    model_id: str
    display_name: str
    provider: ModelProvider
    api_url: Optional[str] = None
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120
    is_default: bool = False
    supported_domains: List[str]
    description: Optional[str] = None
    quantization: Optional[str] = None # e.g., "4bit", "8bit"

class ConfigManager:
    """
    NullAIプロジェクト全体の構成（モデル、ドメイン、一般的な設定）を管理するクラス。
    設定ファイル（JSON形式）から構成をロードし、アクセスを提供します。
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        # backend/app/config.pyから見てプロジェクトルートを指すように調整
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.models_config_path = os.path.join(self.base_dir, 'models_config.json')
        self.domains_config_path = os.path.join(self.base_dir, 'domains_config.json')
        self.null_ai_config_path = os.path.join(self.base_dir, 'null_ai_config.json')

        self.models: Dict[str, ModelConfig] = {}
        self.domains: Dict[str, Any] = {}
        self.null_ai_settings: Dict[str, Any] = {}

        self._load_configs()
        self._initialized = True

    def _load_json_file(self, file_path: str) -> Dict[str, Any]:
        """JSONファイルをロードするヘルパーメソッド"""
        if not os.path.exists(file_path):
            logger.warning(f"Configuration file not found: {file_path}")
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"An unexpected error occurred while reading {file_path}: {e}")
            return {}

    def _load_configs(self):
        """すべての設定ファイルをロードする"""
        logger.info(f"Loading configurations from {self.base_dir}...")

        # null_ai_config.jsonをロード
        self.null_ai_settings = self._load_json_file(self.null_ai_config_path)
        logger.info(f"Loaded null_ai_config.json: {len(self.null_ai_settings)} items")

        # domains_config.jsonをロード
        domains_data = self._load_json_file(self.domains_config_path)
        if "domains" in domains_data and isinstance(domains_data["domains"], list):
            self.domains = {d["domain_id"]: d for d in domains_data["domains"]}
            logger.info(f"Loaded domains_config.json: {len(self.domains)} domains")
        else:
            logger.warning(f"'domains' key not found or not a list in {self.domains_config_path}")
            self.domains = {}

        # models_config.jsonをロード
        models_data = self._load_json_file(self.models_config_path)
        if "models" in models_data and isinstance(models_data["models"], list):
            for model_dict in models_data["models"]:
                try:
                    model = ModelConfig(**model_dict)
                    self.models[model.model_id] = model
                except ValidationError as e:
                    logger.error(f"Validation error for model in {self.models_config_path}: {model_dict} - {e}")
                except Exception as e:
                    logger.error(f"Error processing model {model_dict.get('model_id', 'unknown')}: {e}")
            logger.info(f"Loaded models_config.json: {len(self.models)} models")
        else:
            logger.warning(f"'models' key not found or not a list in {self.models_config_path}")
            self.models = {}

        logger.info("All configurations loaded.")

    def get_model_config(self, model_id: str) -> Optional[ModelConfig]:
        """指定されたモデルIDの構成を取得する"""
        return self.models.get(model_id)

    def get_default_model_config(self, domain_id: Optional[str] = None) -> Optional[ModelConfig]:
        """
        指定されたドメインのデフォルトモデル、またはグローバルデフォルトモデルを取得する。
        """
        if domain_id and domain_id in self.domains and "default_model_id" in self.domains[domain_id]:
            default_model_id = self.domains[domain_id]["default_model_id"]
            model_config = self.get_model_config(default_model_id)
            if model_config:
                return model_config
            logger.warning(f"Default model '{default_model_id}' for domain '{domain_id}' not found in models config.")

        # ドメイン固有のデフォルトが見つからない、または指定がない場合、グローバルデフォルトを探す
        for model_config in self.models.values():
            if model_config.is_default:
                return model_config
        
        logger.warning("No default model found in configuration.")
        return None

    def get_domain_config(self, domain_id: str) -> Optional[Dict[str, Any]]:
        """指定されたドメインIDの構成を取得する"""
        return self.domains.get(domain_id)

    def get_null_ai_setting(self, key: str, default: Any = None) -> Any:
        """null_ai_config.jsonから設定値を取得する"""
        return self.null_ai_settings.get(key, default)

    def reload_configs(self):
        """すべての設定ファイルを再ロードする"""
        logger.info("Reloading configurations...")
        self.models = {}
        self.domains = {}
        self.null_ai_settings = {}
        self._load_configs()
        logger.info("Configurations reloaded.")

# ConfigManagerのシングルトンインスタンス
app_config_manager = ConfigManager()

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

    # ConfigManagerのインスタンスをSettingsに追加
    @property
    def app_config(self) -> ConfigManager:
        return app_config_manager

settings = Settings()
