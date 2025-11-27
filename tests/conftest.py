"""
Pytest configuration for NullAI tests
"""
import pytest
import os
import sys
import tempfile

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def project_root():
    """プロジェクトルートパスを返す"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def temp_config_dir(tmp_path):
    """一時的な設定ディレクトリを作成"""
    return str(tmp_path)


@pytest.fixture(scope="session")
def suppress_deprecation_warnings():
    """非推奨警告を抑制（テスト時のノイズ削減）"""
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    yield
    warnings.resetwarnings()
