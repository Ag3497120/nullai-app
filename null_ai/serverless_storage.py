"""
NullAI サーバーレスストレージモジュール

無料のクラウドストレージバックエンドを提供する。
サーバーレンタル不要で運用可能。

サポートするバックエンド:
1. GitHub Storage - GitHubリポジトリにJSONファイルとして保存
2. Supabase - Supabase無料プラン (PostgreSQL)
3. LocalStorage - クライアントサイドIndexedDB（オフライン対応）
4. JSONBin - 無料JSONストレージサービス
"""
import os
import json
import base64
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx
from dataclasses import dataclass, asdict
import asyncio


@dataclass
class StorageConfig:
    """ストレージ設定"""
    backend: str = "github"  # github, supabase, jsonbin, local
    # GitHub設定
    github_token: str = ""
    github_repo: str = ""  # owner/repo形式
    github_branch: str = "main"
    github_data_path: str = "data"
    # Supabase設定
    supabase_url: str = ""
    supabase_anon_key: str = ""
    # JSONBin設定
    jsonbin_api_key: str = ""
    jsonbin_bin_id: str = ""


class StorageBackend(ABC):
    """ストレージバックエンドの抽象基底クラス"""

    @abstractmethod
    async def get(self, collection: str, doc_id: str) -> Optional[Dict]:
        """ドキュメントを取得"""
        pass

    @abstractmethod
    async def set(self, collection: str, doc_id: str, data: Dict) -> bool:
        """ドキュメントを保存"""
        pass

    @abstractmethod
    async def delete(self, collection: str, doc_id: str) -> bool:
        """ドキュメントを削除"""
        pass

    @abstractmethod
    async def list(self, collection: str, filters: Optional[Dict] = None) -> List[Dict]:
        """ドキュメント一覧を取得"""
        pass

    @abstractmethod
    async def query(self, collection: str, field: str, op: str, value: Any) -> List[Dict]:
        """クエリを実行"""
        pass


class GitHubStorage(StorageBackend):
    """
    GitHub Storageバックエンド

    GitHubリポジトリにJSONファイルとしてデータを保存する。
    完全無料で使用可能（パブリックリポジトリの場合）。

    構造:
    data/
      domains/
        medical.json
        legal.json
      proposals/
        {proposal_id}.json
      tiles/
        {domain}/
          {tile_id}.json
      users/
        {user_id}.json
    """

    def __init__(self, config: StorageConfig):
        self.token = config.github_token
        self.repo = config.github_repo
        self.branch = config.github_branch
        self.data_path = config.github_data_path
        self.base_url = f"https://api.github.com/repos/{self.repo}/contents"
        self._cache = {}
        self._cache_time = {}

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NullAI"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _get_file_path(self, collection: str, doc_id: str) -> str:
        return f"{self.data_path}/{collection}/{doc_id}.json"

    async def get(self, collection: str, doc_id: str) -> Optional[Dict]:
        """GitHubからファイルを取得"""
        file_path = self._get_file_path(collection, doc_id)
        url = f"{self.base_url}/{file_path}?ref={self.branch}"

        # キャッシュチェック（5分間有効）
        cache_key = f"{collection}/{doc_id}"
        if cache_key in self._cache:
            cache_age = (datetime.utcnow() - self._cache_time[cache_key]).total_seconds()
            if cache_age < 300:
                return self._cache[cache_key]

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())

            if response.status_code == 404:
                return None

            if response.status_code != 200:
                print(f"GitHub API error: {response.status_code} - {response.text}")
                return None

            data = response.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            result = json.loads(content)

            # キャッシュに保存
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.utcnow()

            return result

    async def set(self, collection: str, doc_id: str, data: Dict) -> bool:
        """GitHubにファイルを保存"""
        file_path = self._get_file_path(collection, doc_id)
        url = f"{self.base_url}/{file_path}"

        # 既存ファイルのSHAを取得
        sha = None
        async with httpx.AsyncClient() as client:
            check_response = await client.get(
                f"{url}?ref={self.branch}",
                headers=self._get_headers()
            )
            if check_response.status_code == 200:
                sha = check_response.json().get("sha")

            # コンテンツをBase64エンコード
            content = base64.b64encode(
                json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("utf-8")

            # ファイルを作成/更新
            payload = {
                "message": f"Update {collection}/{doc_id}",
                "content": content,
                "branch": self.branch
            }
            if sha:
                payload["sha"] = sha

            response = await client.put(
                url,
                headers=self._get_headers(),
                json=payload
            )

            if response.status_code in [200, 201]:
                # キャッシュを更新
                cache_key = f"{collection}/{doc_id}"
                self._cache[cache_key] = data
                self._cache_time[cache_key] = datetime.utcnow()
                return True

            print(f"GitHub API error: {response.status_code} - {response.text}")
            return False

    async def delete(self, collection: str, doc_id: str) -> bool:
        """GitHubからファイルを削除"""
        file_path = self._get_file_path(collection, doc_id)
        url = f"{self.base_url}/{file_path}"

        async with httpx.AsyncClient() as client:
            # 既存ファイルのSHAを取得
            check_response = await client.get(
                f"{url}?ref={self.branch}",
                headers=self._get_headers()
            )
            if check_response.status_code != 200:
                return False

            sha = check_response.json().get("sha")

            # ファイルを削除
            response = await client.delete(
                url,
                headers=self._get_headers(),
                json={
                    "message": f"Delete {collection}/{doc_id}",
                    "sha": sha,
                    "branch": self.branch
                }
            )

            if response.status_code == 200:
                # キャッシュから削除
                cache_key = f"{collection}/{doc_id}"
                self._cache.pop(cache_key, None)
                self._cache_time.pop(cache_key, None)
                return True

            return False

    async def list(self, collection: str, filters: Optional[Dict] = None) -> List[Dict]:
        """コレクション内の全ドキュメントを取得"""
        url = f"{self.base_url}/{self.data_path}/{collection}?ref={self.branch}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())

            if response.status_code != 200:
                return []

            files = response.json()
            results = []

            for file in files:
                if file["name"].endswith(".json"):
                    doc_id = file["name"][:-5]  # .jsonを除去
                    doc = await self.get(collection, doc_id)
                    if doc:
                        # フィルタリング
                        if filters:
                            match = True
                            for key, value in filters.items():
                                if doc.get(key) != value:
                                    match = False
                                    break
                            if match:
                                results.append(doc)
                        else:
                            results.append(doc)

            return results

    async def query(self, collection: str, field: str, op: str, value: Any) -> List[Dict]:
        """簡易クエリを実行"""
        all_docs = await self.list(collection)
        results = []

        for doc in all_docs:
            doc_value = doc.get(field)
            if op == "==" and doc_value == value:
                results.append(doc)
            elif op == "!=" and doc_value != value:
                results.append(doc)
            elif op == ">" and doc_value is not None and doc_value > value:
                results.append(doc)
            elif op == "<" and doc_value is not None and doc_value < value:
                results.append(doc)
            elif op == "in" and doc_value in value:
                results.append(doc)
            elif op == "contains" and value in str(doc_value):
                results.append(doc)

        return results


class SupabaseStorage(StorageBackend):
    """
    Supabase Storageバックエンド

    Supabase無料プランを使用（PostgreSQL）。
    月間500MB、50,000リクエストまで無料。
    """

    def __init__(self, config: StorageConfig):
        self.url = config.supabase_url
        self.anon_key = config.supabase_anon_key

    def _get_headers(self) -> Dict[str, str]:
        return {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    async def get(self, collection: str, doc_id: str) -> Optional[Dict]:
        """Supabaseからドキュメントを取得"""
        url = f"{self.url}/rest/v1/{collection}?id=eq.{doc_id}&select=*"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())

            if response.status_code != 200:
                return None

            data = response.json()
            return data[0] if data else None

    async def set(self, collection: str, doc_id: str, data: Dict) -> bool:
        """Supabaseにドキュメントを保存（upsert）"""
        url = f"{self.url}/rest/v1/{collection}"
        data["id"] = doc_id
        data["updated_at"] = datetime.utcnow().isoformat()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={**self._get_headers(), "Prefer": "resolution=merge-duplicates"},
                json=data
            )

            return response.status_code in [200, 201]

    async def delete(self, collection: str, doc_id: str) -> bool:
        """Supabaseからドキュメントを削除"""
        url = f"{self.url}/rest/v1/{collection}?id=eq.{doc_id}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=self._get_headers())
            return response.status_code == 200

    async def list(self, collection: str, filters: Optional[Dict] = None) -> List[Dict]:
        """コレクション内の全ドキュメントを取得"""
        url = f"{self.url}/rest/v1/{collection}?select=*"

        if filters:
            for key, value in filters.items():
                url += f"&{key}=eq.{value}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())

            if response.status_code != 200:
                return []

            return response.json()

    async def query(self, collection: str, field: str, op: str, value: Any) -> List[Dict]:
        """Supabaseクエリを実行"""
        op_map = {
            "==": "eq",
            "!=": "neq",
            ">": "gt",
            "<": "lt",
            ">=": "gte",
            "<=": "lte",
            "in": "in",
            "contains": "like"
        }

        supabase_op = op_map.get(op, "eq")
        url = f"{self.url}/rest/v1/{collection}?select=*&{field}={supabase_op}.{value}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())

            if response.status_code != 200:
                return []

            return response.json()


class JSONBinStorage(StorageBackend):
    """
    JSONBin.io Storageバックエンド

    無料プランで10,000リクエスト/月まで使用可能。
    シンプルなJSONストレージサービス。
    """

    def __init__(self, config: StorageConfig):
        self.api_key = config.jsonbin_api_key
        self.bin_id = config.jsonbin_bin_id
        self.base_url = "https://api.jsonbin.io/v3"
        self._data_cache = None
        self._cache_time = None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Master-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def _load_all_data(self) -> Dict:
        """全データを読み込む"""
        # キャッシュチェック（1分間有効）
        if self._data_cache and self._cache_time:
            cache_age = (datetime.utcnow() - self._cache_time).total_seconds()
            if cache_age < 60:
                return self._data_cache

        url = f"{self.base_url}/b/{self.bin_id}/latest"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())

            if response.status_code != 200:
                return {"collections": {}}

            data = response.json().get("record", {"collections": {}})
            self._data_cache = data
            self._cache_time = datetime.utcnow()
            return data

    async def _save_all_data(self, data: Dict) -> bool:
        """全データを保存"""
        url = f"{self.base_url}/b/{self.bin_id}"

        async with httpx.AsyncClient() as client:
            response = await client.put(
                url,
                headers=self._get_headers(),
                json=data
            )

            if response.status_code == 200:
                self._data_cache = data
                self._cache_time = datetime.utcnow()
                return True

            return False

    async def get(self, collection: str, doc_id: str) -> Optional[Dict]:
        """ドキュメントを取得"""
        data = await self._load_all_data()
        return data.get("collections", {}).get(collection, {}).get(doc_id)

    async def set(self, collection: str, doc_id: str, doc_data: Dict) -> bool:
        """ドキュメントを保存"""
        data = await self._load_all_data()

        if "collections" not in data:
            data["collections"] = {}
        if collection not in data["collections"]:
            data["collections"][collection] = {}

        data["collections"][collection][doc_id] = doc_data
        return await self._save_all_data(data)

    async def delete(self, collection: str, doc_id: str) -> bool:
        """ドキュメントを削除"""
        data = await self._load_all_data()

        if collection in data.get("collections", {}):
            if doc_id in data["collections"][collection]:
                del data["collections"][collection][doc_id]
                return await self._save_all_data(data)

        return False

    async def list(self, collection: str, filters: Optional[Dict] = None) -> List[Dict]:
        """コレクション内の全ドキュメントを取得"""
        data = await self._load_all_data()
        docs = list(data.get("collections", {}).get(collection, {}).values())

        if filters:
            filtered = []
            for doc in docs:
                match = True
                for key, value in filters.items():
                    if doc.get(key) != value:
                        match = False
                        break
                if match:
                    filtered.append(doc)
            return filtered

        return docs

    async def query(self, collection: str, field: str, op: str, value: Any) -> List[Dict]:
        """クエリを実行"""
        all_docs = await self.list(collection)
        results = []

        for doc in all_docs:
            doc_value = doc.get(field)
            if op == "==" and doc_value == value:
                results.append(doc)
            elif op == "!=" and doc_value != value:
                results.append(doc)
            elif op == ">" and doc_value is not None and doc_value > value:
                results.append(doc)
            elif op == "<" and doc_value is not None and doc_value < value:
                results.append(doc)

        return results


class LocalFileStorage(StorageBackend):
    """
    ローカルファイルストレージバックエンド

    開発時やオフライン使用時に使用。
    JSONファイルとしてローカルに保存。
    """

    def __init__(self, base_path: str = "./opaque_data"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def _get_collection_path(self, collection: str) -> str:
        path = os.path.join(self.base_path, collection)
        os.makedirs(path, exist_ok=True)
        return path

    def _get_file_path(self, collection: str, doc_id: str) -> str:
        return os.path.join(self._get_collection_path(collection), f"{doc_id}.json")

    async def get(self, collection: str, doc_id: str) -> Optional[Dict]:
        """ローカルファイルからドキュメントを取得"""
        file_path = self._get_file_path(collection, doc_id)

        if not os.path.exists(file_path):
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def set(self, collection: str, doc_id: str, data: Dict) -> bool:
        """ローカルファイルにドキュメントを保存"""
        file_path = self._get_file_path(collection, doc_id)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving file: {e}")
            return False

    async def delete(self, collection: str, doc_id: str) -> bool:
        """ローカルファイルからドキュメントを削除"""
        file_path = self._get_file_path(collection, doc_id)

        if os.path.exists(file_path):
            os.remove(file_path)
            return True

        return False

    async def list(self, collection: str, filters: Optional[Dict] = None) -> List[Dict]:
        """コレクション内の全ドキュメントを取得"""
        collection_path = self._get_collection_path(collection)
        results = []

        for filename in os.listdir(collection_path):
            if filename.endswith(".json"):
                doc_id = filename[:-5]
                doc = await self.get(collection, doc_id)
                if doc:
                    if filters:
                        match = True
                        for key, value in filters.items():
                            if doc.get(key) != value:
                                match = False
                                break
                        if match:
                            results.append(doc)
                    else:
                        results.append(doc)

        return results

    async def query(self, collection: str, field: str, op: str, value: Any) -> List[Dict]:
        """クエリを実行"""
        all_docs = await self.list(collection)
        results = []

        for doc in all_docs:
            doc_value = doc.get(field)
            if op == "==" and doc_value == value:
                results.append(doc)
            elif op == "!=" and doc_value != value:
                results.append(doc)
            elif op == ">" and doc_value is not None and doc_value > value:
                results.append(doc)
            elif op == "<" and doc_value is not None and doc_value < value:
                results.append(doc)

        return results


def create_storage(config: Optional[StorageConfig] = None) -> StorageBackend:
    """
    設定に基づいてストレージバックエンドを作成する。

    環境変数から設定を読み込む場合:
    - OPAQUE_STORAGE_BACKEND: github, supabase, jsonbin, local
    - GITHUB_TOKEN, GITHUB_REPO, etc.
    - SUPABASE_URL, SUPABASE_ANON_KEY
    - JSONBIN_API_KEY, JSONBIN_BIN_ID
    """
    if config is None:
        config = StorageConfig(
            backend=os.getenv("OPAQUE_STORAGE_BACKEND", "local"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_repo=os.getenv("GITHUB_REPO", ""),
            github_branch=os.getenv("GITHUB_BRANCH", "main"),
            github_data_path=os.getenv("GITHUB_DATA_PATH", "data"),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
            jsonbin_api_key=os.getenv("JSONBIN_API_KEY", ""),
            jsonbin_bin_id=os.getenv("JSONBIN_BIN_ID", "")
        )

    if config.backend == "github":
        return GitHubStorage(config)
    elif config.backend == "supabase":
        return SupabaseStorage(config)
    elif config.backend == "jsonbin":
        return JSONBinStorage(config)
    else:
        return LocalFileStorage()


# グローバルストレージインスタンス
_storage: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    """グローバルストレージインスタンスを取得"""
    global _storage
    if _storage is None:
        _storage = create_storage()
    return _storage


def set_storage(storage: StorageBackend):
    """グローバルストレージインスタンスを設定"""
    global _storage
    _storage = storage
