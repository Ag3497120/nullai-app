"""
NullAI テストスイート

null_ai モジュールのユニットテストと統合テスト
"""
import pytest
import asyncio
import os
import sys
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from null_ai.config import (
    ModelProvider,
    ModelConfig,
    DomainConfig,
    NullAIConfig,
    ConfigManager,
    DEFAULT_MODELS,
    DEFAULT_DOMAINS
)


class TestModelProvider:
    """ModelProvider Enum テスト"""

    def test_huggingface_provider_exists(self):
        """HuggingFaceプロバイダーが存在する"""
        assert ModelProvider.HUGGINGFACE.value == "huggingface"

    def test_huggingface_api_provider_exists(self):
        """HuggingFace APIプロバイダーが存在する"""
        assert ModelProvider.HUGGINGFACE_API.value == "huggingface_api"

    def test_local_provider_exists(self):
        """Localプロバイダーが存在する"""
        assert ModelProvider.LOCAL.value == "local"

    def test_gguf_provider_exists(self):
        """GGUFプロバイダーが存在する"""
        assert ModelProvider.GGUF.value == "gguf"

    def test_no_external_api_providers(self):
        """外部APIプロバイダー（OpenAI/Anthropic/Ollama）が存在しない"""
        provider_values = [p.value for p in ModelProvider]
        assert "openai" not in provider_values
        assert "anthropic" not in provider_values
        # Ollamaは下位互換性のために残る場合があるが、推奨されない
        # assert "ollama" not in provider_values


class TestModelConfig:
    """ModelConfig テスト"""

    def test_create_huggingface_model(self):
        """HuggingFaceモデル設定を作成できる"""
        config = ModelConfig(
            model_id="test-model",
            display_name="Test Model",
            provider=ModelProvider.HUGGINGFACE,
            model_name="test-org/test-model"
        )
        assert config.model_id == "test-model"
        assert config.provider == ModelProvider.HUGGINGFACE

    def test_model_to_dict(self):
        """ModelConfigを辞書に変換できる"""
        config = ModelConfig(
            model_id="test-model",
            display_name="Test Model",
            provider=ModelProvider.HUGGINGFACE,
            model_name="test-org/test-model"
        )
        d = config.to_dict()
        assert d["model_id"] == "test-model"
        assert d["provider"] == "huggingface"

    def test_model_from_dict(self):
        """辞書からModelConfigを作成できる"""
        data = {
            "model_id": "test-model",
            "display_name": "Test Model",
            "provider": "huggingface",
            "model_name": "test-org/test-model"
        }
        config = ModelConfig.from_dict(data)
        assert config.model_id == "test-model"
        assert config.provider == ModelProvider.HUGGINGFACE


class TestDefaultModels:
    """DEFAULT_MODELS テスト"""

    def test_default_models_exist(self):
        """デフォルトモデルが存在する"""
        assert len(DEFAULT_MODELS) > 0

    def test_default_models_use_huggingface(self):
        """デフォルトモデルはHuggingFaceプロバイダーを使用"""
        for model in DEFAULT_MODELS:
            assert model.provider in [
                ModelProvider.HUGGINGFACE,
                ModelProvider.HUGGINGFACE_API,
                ModelProvider.LOCAL,
                ModelProvider.GGUF
            ], f"Model {model.model_id} uses unsupported provider {model.provider}"

    def test_has_default_model(self):
        """デフォルトモデルが設定されている"""
        default_models = [m for m in DEFAULT_MODELS if m.is_default]
        assert len(default_models) >= 1

    def test_deepseek_models_exist(self):
        """DeepSeekモデルが存在する"""
        deepseek_models = [m for m in DEFAULT_MODELS if "deepseek" in m.model_id.lower()]
        assert len(deepseek_models) > 0


class TestDefaultDomains:
    """DEFAULT_DOMAINS テスト"""

    def test_default_domains_exist(self):
        """デフォルトドメインが存在する"""
        assert len(DEFAULT_DOMAINS) > 0

    def test_medical_domain_exists(self):
        """医療ドメインが存在する"""
        medical = [d for d in DEFAULT_DOMAINS if d.domain_id == "medical"]
        assert len(medical) == 1

    def test_legal_domain_exists(self):
        """法律ドメインが存在する"""
        legal = [d for d in DEFAULT_DOMAINS if d.domain_id == "legal"]
        assert len(legal) == 1

    def test_general_domain_exists(self):
        """一般ドメインが存在する"""
        general = [d for d in DEFAULT_DOMAINS if d.domain_id == "general"]
        assert len(general) == 1


class TestNullAIConfig:
    """NullAIConfig テスト"""

    def test_default_config(self):
        """デフォルト設定を作成できる"""
        config = NullAIConfig()
        assert config.system_name == "NullAI"
        assert config.version == "1.0.0"

    def test_config_to_dict(self):
        """設定を辞書に変換できる"""
        config = NullAIConfig()
        d = config.to_dict()
        assert "system_name" in d
        assert "version" in d
        assert "default_model_id" in d


class TestConfigManager:
    """ConfigManager テスト"""

    def test_create_config_manager(self, tmp_path):
        """ConfigManagerを作成できる"""
        manager = ConfigManager(config_dir=str(tmp_path))
        assert manager is not None

    def test_list_models(self, tmp_path):
        """モデル一覧を取得できる"""
        manager = ConfigManager(config_dir=str(tmp_path))
        models = manager.list_models()
        assert len(models) > 0

    def test_list_domains(self, tmp_path):
        """ドメイン一覧を取得できる"""
        manager = ConfigManager(config_dir=str(tmp_path))
        domains = manager.list_domains()
        assert len(domains) > 0

    def test_get_default_model(self, tmp_path):
        """デフォルトモデルを取得できる"""
        manager = ConfigManager(config_dir=str(tmp_path))
        default = manager.get_default_model()
        assert default is not None
        assert default.is_default

    def test_get_model_by_id(self, tmp_path):
        """IDでモデルを取得できる"""
        manager = ConfigManager(config_dir=str(tmp_path))
        # デフォルトモデルIDで取得
        model = manager.get_model("deepseek-r1-32b")
        assert model is not None
        assert model.model_id == "deepseek-r1-32b"

    def test_get_domain_by_id(self, tmp_path):
        """IDでドメインを取得できる"""
        manager = ConfigManager(config_dir=str(tmp_path))
        domain = manager.get_domain("medical")
        assert domain is not None
        assert domain.domain_id == "medical"


class TestModelRouter:
    """ModelRouter テスト（モックを使用）"""

    @pytest.fixture
    def mock_config_manager(self, tmp_path):
        """モックConfigManager"""
        return ConfigManager(config_dir=str(tmp_path))

    def test_create_model_router(self, mock_config_manager):
        """ModelRouterを作成できる"""
        from null_ai.model_router import ModelRouter
        router = ModelRouter(mock_config_manager)
        assert router is not None

    def test_get_model_for_domain(self, mock_config_manager):
        """ドメインに対応するモデルを取得できる"""
        from null_ai.model_router import ModelRouter
        router = ModelRouter(mock_config_manager)
        model = router.get_model_for_domain("medical")
        assert model is not None

    def test_get_provider_info(self, mock_config_manager):
        """プロバイダー情報を取得できる"""
        from null_ai.model_router import ModelRouter
        router = ModelRouter(mock_config_manager)
        info = router.get_provider_info()

        assert "supported_providers" in info
        assert "unsupported_providers" in info

        # サポートされているプロバイダーを確認
        supported_ids = [p["id"] for p in info["supported_providers"]]
        assert "huggingface" in supported_ids
        assert "huggingface_api" in supported_ids
        assert "gguf" in supported_ids

        # サポートされていないプロバイダーを確認
        unsupported_ids = [p["id"] for p in info["unsupported_providers"]]
        assert "openai" in unsupported_ids
        assert "anthropic" in unsupported_ids

    @pytest.mark.asyncio
    async def test_list_available_models(self, mock_config_manager):
        """利用可能なモデル一覧を取得できる"""
        from null_ai.model_router import ModelRouter
        router = ModelRouter(mock_config_manager)
        models = await router.list_available_models()
        assert len(models) > 0


class TestWebSearchEnrichment:
    """WebSearchEnrichment テスト"""

    def test_create_enrichment_engine(self):
        """WebSearchEnrichmentを作成できる"""
        from null_ai.web_search_enrichment import WebSearchEnrichment
        enricher = WebSearchEnrichment()
        assert enricher is not None

    def test_generate_search_queries(self):
        """検索クエリを生成できる"""
        from null_ai.web_search_enrichment import WebSearchEnrichment
        enricher = WebSearchEnrichment()
        queries = enricher.generate_search_queries("medical", count=5)
        assert len(queries) > 0
        assert len(queries) <= 5

    def test_duckduckgo_provider_always_available(self):
        """DuckDuckGoプロバイダーが常に利用可能"""
        from null_ai.web_search_enrichment import WebSearchEnrichment
        enricher = WebSearchEnrichment()
        provider_names = [p.__class__.__name__ for p in enricher.search_providers]
        assert "DuckDuckGoSearch" in provider_names


class TestSystemAPI:
    """System API テスト"""

    @pytest.fixture
    def client(self):
        """FastAPIテストクライアント"""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        return TestClient(app)

    def test_system_status_endpoint(self, client):
        """/api/system/status エンドポイントが動作する"""
        response = client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data
        assert "models" in data

    def test_system_health_endpoint(self, client):
        """/api/system/health エンドポイントが動作する"""
        response = client.get("/api/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_providers_endpoint(self, client):
        """/api/system/providers エンドポイントが動作する"""
        response = client.get("/api/system/providers")
        assert response.status_code == 200
        data = response.json()
        assert "supported" in data
        assert "unsupported" in data


# 統合テスト（オプション - 実際のモデルが必要）
class TestIntegration:
    """統合テスト（実行には実際のモデルが必要）"""

    @pytest.mark.skip(reason="Requires actual model download")
    @pytest.mark.asyncio
    async def test_inference_with_huggingface(self, tmp_path):
        """HuggingFaceモデルで推論が実行できる"""
        from null_ai.config import ConfigManager
        from null_ai.model_router import ModelRouter

        manager = ConfigManager(config_dir=str(tmp_path))
        router = ModelRouter(manager)

        result = await router.infer(
            prompt="Hello, how are you?",
            domain_id="general",
            save_to_memory=False,
            max_tokens=50
        )

        assert "response" in result
        assert len(result["response"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
