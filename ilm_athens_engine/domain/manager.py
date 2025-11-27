import json
from typing import Dict, Any

class DomainManager:
    """
    domain_schemas.json からドメイン定義を読み込み、管理します。
    これにより、システムは各ドメインの詳細（軸、キーワード等）を動的に扱えます。
    """
    _instance = None

    def __new__(cls, schema_path='domain_schemas.json'):
        if cls._instance is None:
            cls._instance = super(DomainManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, schema_path: str = 'domain_schemas.json'):
        if self._initialized:
            return
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                self.schemas: Dict[str, Any] = json.load(f)
            print(f"ドメインスキーマを '{schema_path}' から正常に読み込みました。")
            print(f"利用可能なドメイン: {list(self.schemas.keys())}")
        except FileNotFoundError:
            print(f"エラー: ドメインスキーマファイル '{schema_path}' が見つかりません。")
            self.schemas = {}
        except json.JSONDecodeError:
            print(f"エラー: ドメインスキーマファイル '{schema_path}' のJSON形式が正しくありません。")
            self.schemas = {}
        self._initialized = True

    def get_schema(self, domain_id: str) -> Dict[str, Any]:
        """
        指定されたドメインIDのスキーマを返します。

        Args:
            domain_id (str): 取得したいドメインのID (例: "medical", "legal")。

        Returns:
            Dict[str, Any]: ドメインスキーマの辞書。見つからない場合はNoneを返します。
        """
        return self.schemas.get(domain_id)

    def list_domains(self) -> list:
        """
        利用可能なすべてのドメインIDのリストを返します。
        """
        return list(self.schemas.keys())

# --- 使用例 ---
if __name__ == '__main__':
    # DomainManagerはシングルトンとして振る舞う
    domain_manager = DomainManager()
    
    # 医学ドメインのスキーマを取得
    print("\n--- 'medical' ドメインスキーマの取得 ---")
    medical_schema = domain_manager.get_schema("medical")
    if medical_schema:
        print(f"ドメイン名: {medical_schema['domain_name']}")
        print(f"X軸の名前: {medical_schema['axes']['x_axis']['name']}")
        print(f"キーワード '心臓' のマッピング: {medical_schema['keyword_map']['心臓']}")

    # 法学ドメインのスキーマを取得
    print("\n--- 'legal' ドメインスキーマの取得 ---")
    legal_schema = domain_manager.get_schema("legal")
    if legal_schema:
        print(f"ドメイン名: {legal_schema['domain_name']}")
        print(f"Y軸の名前: {legal_schema['axes']['y_axis']['name']}")
        print(f"キーワード '判例' のマッピング: {legal_schema['keyword_map']['判例']}")

    # 存在しないドメイン
    print("\n--- 存在しないドメインの取得 ---")
    unknown_schema = domain_manager.get_schema("unknown_domain")
    print(f"結果: {unknown_schema}")
