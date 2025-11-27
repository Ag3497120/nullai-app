"""
NullAI クラウドDB設定スクリプト

無料のクラウドデータベースをセットアップする。
サポートするサービス:
- Supabase (推奨): 500MB無料、PostgreSQL
- GitHub: 無制限（パブリックリポジトリ）
- JSONBin: 10,000リクエスト/月無料

使用方法:
    python null_ai/cloud_db_setup.py --provider supabase
    python null_ai/cloud_db_setup.py --provider github --repo username/null-data
"""
import os
import sys
import json
import argparse
import httpx
import asyncio
from datetime import datetime


class SupabaseSetup:
    """Supabase無料プランのセットアップ"""

    TABLES_SQL = """
-- ドメインテーブル
CREATE TABLE IF NOT EXISTS domains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    axes JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 提案テーブル
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    proposal_type TEXT NOT NULL,
    domain_id TEXT REFERENCES domains(id),
    tile_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    proposed_content JSONB,
    proposed_coordinates JSONB,
    justification TEXT,
    status TEXT DEFAULT 'pending',
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    reviewer_comment TEXT,
    validation_score FLOAT,
    creator_is_expert BOOLEAN DEFAULT FALSE,
    creator_orcid_id TEXT,
    creator_display_name TEXT,
    reviewer_is_expert BOOLEAN DEFAULT FALSE,
    reviewer_orcid_id TEXT,
    reviewer_display_name TEXT,
    verification_mark JSONB
);

-- 知識タイルテーブル
CREATE TABLE IF NOT EXISTS tiles (
    id TEXT PRIMARY KEY,
    domain_id TEXT REFERENCES domains(id),
    content JSONB NOT NULL,
    coordinates JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT,
    is_expert_verified BOOLEAN DEFAULT FALSE,
    expert_orcid_id TEXT,
    source_type TEXT DEFAULT 'user'  -- user, llm, web_search
);

-- ユーザーテーブル
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    role TEXT DEFAULT 'viewer',
    is_expert BOOLEAN DEFAULT FALSE,
    orcid_id TEXT,
    display_name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Row Level Security (RLS) を有効化
ALTER TABLE domains ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE tiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 読み取りは全員許可（ゲストアクセス対応）
CREATE POLICY "Allow public read access" ON domains FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON proposals FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON tiles FOR SELECT USING (true);

-- 書き込みは認証済みユーザーのみ
CREATE POLICY "Allow authenticated insert" ON proposals FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated insert" ON tiles FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_domain ON proposals(domain_id);
CREATE INDEX IF NOT EXISTS idx_tiles_domain ON tiles(domain_id);
CREATE INDEX IF NOT EXISTS idx_tiles_expert ON tiles(is_expert_verified);
"""

    @staticmethod
    def print_setup_instructions():
        print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     Supabase 無料クラウドDB セットアップ                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

【手順】

1. Supabaseアカウント作成（無料）
   https://supabase.com にアクセスし、GitHubでサインアップ

2. 新規プロジェクト作成
   - 「New Project」をクリック
   - プロジェクト名: null-ai
   - リージョン: Northeast Asia (Tokyo) 推奨
   - パスワード: 安全なパスワードを設定

3. APIキーを取得
   - Settings > API に移動
   - 「Project URL」と「anon public」キーをコピー

4. テーブル作成
   - SQL Editor に移動
   - 以下のSQLを実行:

""")
        print(SupabaseSetup.TABLES_SQL)
        print("""

5. 環境変数を設定
   .envファイルに追加:

   OPAQUE_STORAGE_BACKEND=supabase
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_ANON_KEY=eyJxxxxxxxxxxxxxxxx

6. 初期データを投入
   python null_ai/cloud_db_setup.py --provider supabase --init-data

【無料枠】
- ストレージ: 500MB
- リクエスト: 50,000/月
- 帯域: 2GB/月
""")


class GitHubStorageSetup:
    """GitHub Storageのセットアップ"""

    INITIAL_STRUCTURE = {
        "data/domains/medical.json": {
            "domain_id": "medical",
            "name": "Medical",
            "description": "医療・健康に関する知識領域",
            "axes": [
                {"name": "診断", "description": "症状から疾患を特定", "keywords": ["症状", "検査", "診断"]},
                {"name": "治療", "description": "治療法と薬物療法", "keywords": ["治療", "薬", "手術"]},
                {"name": "予防", "description": "疾病予防と健康管理", "keywords": ["予防", "検診", "ワクチン"]}
            ]
        },
        "data/domains/legal.json": {
            "domain_id": "legal",
            "name": "Legal",
            "description": "法律・法務に関する知識領域",
            "axes": [
                {"name": "民法", "description": "民事法関連", "keywords": ["契約", "損害賠償", "相続"]},
                {"name": "刑法", "description": "刑事法関連", "keywords": ["犯罪", "刑罰", "告訴"]},
                {"name": "商法", "description": "商事法関連", "keywords": ["会社", "取引", "株式"]}
            ]
        },
        "data/domains/economics.json": {
            "domain_id": "economics",
            "name": "Economics",
            "description": "経済・金融に関する知識領域",
            "axes": [
                {"name": "マクロ経済", "description": "国家・世界経済", "keywords": ["GDP", "インフレ", "金融政策"]},
                {"name": "ミクロ経済", "description": "市場・企業経済", "keywords": ["需要", "供給", "価格"]},
                {"name": "金融", "description": "金融市場・投資", "keywords": ["株式", "債券", "為替"]}
            ]
        },
        "data/README.md": "# NullAI Data Repository\n\nThis repository stores NullAI knowledge base data.\n"
    }

    @staticmethod
    def print_setup_instructions(repo_name: str = "username/opaque-data"):
        print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     GitHub Storage 無料セットアップ                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

【手順】

1. データ保存用リポジトリを作成
   - GitHub.com で新規リポジトリ作成
   - 名前: opaque-data
   - Public（無料で無制限）またはPrivate

2. Personal Access Token (PAT) を生成
   - Settings > Developer settings > Personal access tokens
   - 「Generate new token (classic)」をクリック
   - スコープ: 「repo」にチェック
   - トークンをコピー（一度しか表示されない）

3. 初期データをプッシュ
   git clone https://github.com/{repo_name}.git
   cd opaque-data
   mkdir -p data/domains data/tiles data/proposals

   # 初期ドメインデータを作成（省略）

   git add .
   git commit -m "Initial data structure"
   git push

4. 環境変数を設定
   .envファイルに追加:

   OPAQUE_STORAGE_BACKEND=github
   GITHUB_TOKEN=ghp_xxxxxxxxxxxx
   GITHUB_REPO={repo_name}
   GITHUB_BRANCH=main
   GITHUB_DATA_PATH=data

【メリット】
- 完全無料（パブリックリポジトリ）
- バージョン管理自動対応
- 変更履歴の透明性
- GitHub Pages でDBを公開可能
""")


class JSONBinSetup:
    """JSONBin.io のセットアップ"""

    INITIAL_DATA = {
        "collections": {
            "domains": {
                "medical": {
                    "domain_id": "medical",
                    "name": "Medical",
                    "description": "医療・健康に関する知識領域"
                },
                "legal": {
                    "domain_id": "legal",
                    "name": "Legal",
                    "description": "法律・法務に関する知識領域"
                }
            },
            "proposals": {},
            "tiles": {}
        },
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    }

    @staticmethod
    def print_setup_instructions():
        print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     JSONBin.io 無料セットアップ                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

【手順】

1. JSONBin.ioアカウント作成（無料）
   https://jsonbin.io にアクセスし、サインアップ

2. APIキーを取得
   - ダッシュボードの「API Keys」から取得
   - Master Keyをコピー

3. 新しいBinを作成
   - 「Create a Bin」をクリック
   - 以下の初期データを貼り付け:

""")
        print(json.dumps(JSONBinSetup.INITIAL_DATA, indent=2, ensure_ascii=False))
        print("""

4. Bin IDを取得
   - 作成されたBinのIDをコピー（URLの最後の部分）

5. 環境変数を設定
   .envファイルに追加:

   OPAQUE_STORAGE_BACKEND=jsonbin
   JSONBIN_API_KEY=$2b$xxxxxxxx
   JSONBIN_BIN_ID=xxxxxxxxxxxxxxxx

【無料枠】
- リクエスト: 10,000/月
- Bin数: 無制限
- ストレージ: 制限なし
""")


async def init_supabase_data(url: str, key: str):
    """Supabaseに初期データを投入"""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    initial_domains = [
        {
            "id": "medical",
            "name": "Medical",
            "description": "医療・健康に関する知識領域",
            "axes": json.dumps([
                {"name": "診断", "description": "症状から疾患を特定"},
                {"name": "治療", "description": "治療法と薬物療法"},
                {"name": "予防", "description": "疾病予防と健康管理"}
            ])
        },
        {
            "id": "legal",
            "name": "Legal",
            "description": "法律・法務に関する知識領域",
            "axes": json.dumps([
                {"name": "民法", "description": "民事法関連"},
                {"name": "刑法", "description": "刑事法関連"},
                {"name": "商法", "description": "商事法関連"}
            ])
        },
        {
            "id": "economics",
            "name": "Economics",
            "description": "経済・金融に関する知識領域",
            "axes": json.dumps([
                {"name": "マクロ経済", "description": "国家・世界経済"},
                {"name": "ミクロ経済", "description": "市場・企業経済"},
                {"name": "金融", "description": "金融市場・投資"}
            ])
        }
    ]

    async with httpx.AsyncClient() as client:
        for domain in initial_domains:
            response = await client.post(
                f"{url}/rest/v1/domains",
                headers=headers,
                json=domain
            )
            if response.status_code in [200, 201]:
                print(f"  [OK] Domain '{domain['id']}' created")
            elif response.status_code == 409:
                print(f"  [SKIP] Domain '{domain['id']}' already exists")
            else:
                print(f"  [ERROR] Domain '{domain['id']}': {response.text}")


def main():
    parser = argparse.ArgumentParser(description="NullAI Cloud DB Setup")
    parser.add_argument("--provider", choices=["supabase", "github", "jsonbin"],
                        default="supabase", help="Cloud provider to set up")
    parser.add_argument("--repo", type=str, help="GitHub repo (username/repo)")
    parser.add_argument("--init-data", action="store_true",
                        help="Initialize with sample data")

    args = parser.parse_args()

    if args.provider == "supabase":
        SupabaseSetup.print_setup_instructions()
        if args.init_data:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_ANON_KEY")
            if url and key:
                print("\n初期データを投入中...")
                asyncio.run(init_supabase_data(url, key))
                print("完了!")
            else:
                print("\n[ERROR] SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment")

    elif args.provider == "github":
        repo = args.repo or "username/opaque-data"
        GitHubStorageSetup.print_setup_instructions(repo)

    elif args.provider == "jsonbin":
        JSONBinSetup.print_setup_instructions()


if __name__ == "__main__":
    main()
