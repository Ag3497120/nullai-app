# NullAI システム起動ガイド

## 概要

NullAIは、マルチドメイン対応の知識推論システムです。医療、法律、経済、プログラミングなど、複数の専門領域に対応し、ユーザーが自由にLLMモデルやドメインを追加・管理できます。

### 主な特徴

- **ゲストアクセス**: 登録不要でシステムを利用可能
- **ORCID認証**: 専門家はORCIDで認証し、編集内容に認証マークが付与される
- **サーバーレス対応**: GitHub/Supabase/JSONBinを使用した無料ストレージ
- **HuggingFace対応**: Transformers、Inference API、GGUF形式をサポート
- **樹木型空間記憶**: DendriticMemorySpaceによる効率的な知識管理

> **重要**: OpenAI/Anthropic/Ollama等の外部APIは利用規約上の理由から削除されました。
> NullAIはHuggingFace Transformersおよびオープンソースモデルのみをサポートします。

## システム要件

- Python 3.10以上
- Node.js 18以上
- GPU（推奨: CUDA対応 または Apple Silicon MPS）
- PostgreSQL（オプション、SQLiteでも動作）
- ORCID開発者アカウント（専門家認証機能使用時）

## クイックスタート

### 1. 環境構築

```bash
# リポジトリのクローン（または既存ディレクトリへ移動）
cd project_locate

# Python仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Python依存パッケージのインストール
pip install -r requirements.txt

# フロントエンド依存パッケージのインストール
cd frontend
npm install
cd ..
```

### 2. HuggingFace Transformersのセットアップ

```bash
# 必要なPythonパッケージのインストール
pip install transformers torch accelerate

# GPU確認
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, MPS: {torch.backends.mps.is_available()}')"

# モデルの事前ダウンロード（オプション - 初回実行時に自動ダウンロードされる）
python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; AutoTokenizer.from_pretrained('deepseek-ai/DeepSeek-R1-Distill-Qwen-7B')"

# GGUF形式を使用する場合（CPU環境向け）
pip install llama-cpp-python
```

### 3. 環境変数の設定

```bash
# .envファイルを作成
cat > .env << 'EOF'
# API設定
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=true
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# データベース
DATABASE_URL=sqlite:///./sql_app.db

# HuggingFace設定（オプション - Inference APIを使用する場合）
# HF_API_KEY=hf_xxx

# ========================================
# 以下のAPIは利用規約上の理由からサポートされていません:
# - OPENAI_API_KEY (OpenAI)
# - ANTHROPIC_API_KEY (Anthropic)
# - OLLAMA_URL (Ollama)
# HuggingFace Transformersを使用してください。
# ========================================

# ORCID認証（専門家認証機能使用時）
# ORCID_CLIENT_ID=APP-XXXXXXXXX
# ORCID_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# ORCID_REDIRECT_URI=http://localhost:8000/api/auth/orcid/callback
# ORCID_SANDBOX=true  # 開発時はtrue、本番はfalse

# サーバーレスストレージ設定（オプション）
# OPAQUE_STORAGE_BACKEND=local  # local, github, supabase, jsonbin

# GitHub Storage
# GITHUB_TOKEN=ghp_xxxxxxxxxxxx
# GITHUB_REPO=username/opaque-data
# GITHUB_BRANCH=main
# GITHUB_DATA_PATH=data

# Supabase Storage
# SUPABASE_URL=https://xxxxx.supabase.co
# SUPABASE_ANON_KEY=eyJxxxxxxxx

# JSONBin Storage
# JSONBIN_API_KEY=$2b$xxxxxxxx
# JSONBIN_BIN_ID=xxxxxxxxxxxxxxxx
EOF
```

### 4. データベース初期化

```bash
# データベーステーブルの作成
python backend/create_db.py
```

### 5. システムの起動

#### 方法A: 個別起動（開発時推奨）

```bash
# ターミナル1: バックエンドAPIサーバー
cd project_locate
source venv/bin/activate
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# ターミナル2: フロントエンド開発サーバー
cd project_locate/frontend
npm run dev
```

#### 方法B: Docker Compose（本番環境推奨）

```bash
# Docker Composeで全サービスを起動
docker-compose up -d

# ログの確認
docker-compose logs -f
```

### 6. アクセス

- **フロントエンド**: http://localhost:5173
- **バックエンドAPI**: http://localhost:8000
- **API ドキュメント**: http://localhost:8000/docs
- **Ollama**: http://localhost:11434

## 初期設定

### ユーザー登録

1. http://localhost:5173 にアクセス
2. 「Sign up」をクリック
3. メールアドレスとパスワードを入力して登録

### 管理者権限の付与

```bash
# SQLiteの場合
sqlite3 sql_app.db "UPDATE users SET role='admin' WHERE email='your@email.com';"

# または Python スクリプトで
python -c "
from backend.app.database.session import SessionLocal
from backend.app.database.models import User
db = SessionLocal()
user = db.query(User).filter(User.email=='your@email.com').first()
user.role = 'admin'
db.commit()
print('Admin role granted')
"
```

## DB拡充コマンド

### 基本的な使い方

```bash
# ヘルプを表示
python null_ai/db_enrichment_cli.py --help

# 利用可能なモデル一覧
python null_ai/db_enrichment_cli.py --list-models

# 利用可能なドメイン一覧
python null_ai/db_enrichment_cli.py --list-domains

# 生成される質問をプレビュー（実行しない）
python null_ai/db_enrichment_cli.py --domain medical --preview --count 20
```

### DB拡充の実行

```bash
# 医療ドメインを50件の質問で拡充
python null_ai/db_enrichment_cli.py --domain medical --count 50

# 全ドメインを拡充（各30件）
python null_ai/db_enrichment_cli.py --all --count 30

# 特定のモデルを使用して拡充
python null_ai/db_enrichment_cli.py --domain legal --model deepseek-r1-32b --count 20

# バッチサイズを指定（レート制限対策）
python null_ai/db_enrichment_cli.py --domain economics --count 100 --batch-size 3
```

### Web検索による拡充

Web検索を使用して最新情報を収集し、DBを拡充できます：

```bash
# Web検索で最新情報を収集（DuckDuckGo、無料・キー不要）
python null_ai/db_enrichment_cli.py --domain medical --web-search --count 10

# 特定のクエリでWeb検索
python null_ai/db_enrichment_cli.py --domain medical --web-search --query "最新の糖尿病治療法 2024"

# クエリファイルから検索
python null_ai/db_enrichment_cli.py --domain legal --web-search --queries-file legal_queries.txt

# 利用可能な検索プロバイダーを確認
python null_ai/db_enrichment_cli.py --list-search-providers
```

#### 追加の検索プロバイダー（オプション）

より高品質な検索結果を得るには、以下の無料APIを設定できます：

```bash
# Brave Search API（無料2,000クエリ/月）
# https://brave.com/search/api/ で取得
BRAVE_API_KEY=your-brave-api-key

# Tavily AI Search（AI最適化検索）
# https://tavily.com/ で取得
TAVILY_API_KEY=your-tavily-api-key
```

### 拡充結果

結果は `enrichment_output/` ディレクトリにJSON形式で保存されます：

```
enrichment_output/
├── enrichment_medical_20241124_120000.json
├── enrichment_legal_20241124_121500.json
├── web_enrichment_medical_20241124_130000.json  # Web検索結果
└── ...
```

## モデル管理

### Web UIでのモデル追加

1. 管理者としてログイン
2. 「Settings」→「Models」に移動
3. 「Add Model」をクリック
4. 必要な情報を入力:
   - Model ID: 一意の識別子（例: `custom-medical-llm`）
   - Display Name: 表示名
   - Provider: `huggingface`, `huggingface_api`, `local`, `gguf`
   - Model Name: HuggingFaceモデルID（例: `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`）
   - Supported Domains: 対応ドメイン

> **サポートされていないプロバイダー**: `openai`, `anthropic`, `ollama` は利用規約上の理由から削除されました。

### APIでのモデル追加

```bash
# HuggingFaceモデルを追加
curl -X POST http://localhost:8000/api/models/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "qwen2-72b",
    "display_name": "Qwen2.5 72B",
    "provider": "huggingface",
    "model_name": "Qwen/Qwen2.5-72B-Instruct",
    "supported_domains": ["medical", "legal", "general"],
    "description": "高性能多言語モデル"
  }'

# モデル接続テスト
curl -X POST http://localhost:8000/api/models/qwen2-72b/test \
  -H "Authorization: Bearer YOUR_TOKEN"

# サポートされているプロバイダー情報を取得
curl http://localhost:8000/api/models/providers/info
```

## ドメイン管理

### 新しいドメインの追加

1. Web UIの「Domains」タブで追加
2. または `domains_config.json` を直接編集:

```json
{
  "domains": [
    {
      "domain_id": "philosophy",
      "name": "Philosophy",
      "description": "哲学・思想に関する知識領域",
      "default_model_id": "deepseek-r1-32b",
      "icon": "philosophy",
      "is_active": true
    }
  ]
}
```

### ドメイン固有の質問テンプレート追加

`null_ai/db_enrichment_cli.py` の `DOMAIN_QUESTION_TEMPLATES` に追加:

```python
"philosophy": {
    "categories": [
        {
            "name": "哲学者",
            "questions": [
                "{philosopher}の主要な思想は何ですか？",
                "{philosopher}の代表的な著作について教えてください。",
            ]
        }
    ],
    "topics": {
        "philosopher": ["プラトン", "アリストテレス", "カント", "ニーチェ"]
    }
}
```

## ORCID認証の設定

### 1. ORCID開発者アカウントの作成

1. https://orcid.org/developer-tools にアクセス
2. 「Register for the free ORCID public API」をクリック
3. アプリケーション情報を入力:
   - **Application Name**: NullAI
   - **Website URL**: http://localhost:5173 (開発時)
   - **Redirect URIs**: http://localhost:8000/api/auth/orcid/callback
4. Client IDとClient Secretを取得

### 2. 開発用サンドボックス

開発時はORCIDサンドボックス環境を使用できます:
- サンドボックス: https://sandbox.orcid.org
- `.env`で`ORCID_SANDBOX=true`を設定

### 3. 本番環境

本番環境では:
- 本番用ORCID認証情報を取得
- `.env`で`ORCID_SANDBOX=false`を設定
- Redirect URIを本番URLに更新

## ユーザーロールとアクセスレベル

| ロール | 説明 | 権限 |
|-------|------|-----|
| guest | 未登録ユーザー | 閲覧、質問 |
| viewer | 登録ユーザー | + 提案の閲覧 |
| editor | 編集者 | + 提案の作成・レビュー |
| expert | ORCID認証済み専門家 | + 認証マーク付き編集 |
| admin | 管理者 | + 全管理機能 |

### 認証マークの種類

- **none**: 未検証
- **community**: コミュニティレビュー済み
- **expert**: ORCID認証専門家による編集/レビュー
- **multi_expert**: 複数の専門家による検証

## サーバーレスストレージ設定

### GitHub Storage（推奨）

GitHubリポジトリをデータベースとして使用:

1. データ保存用リポジトリを作成
2. Personal Access Token (PAT)を生成:
   - Settings > Developer settings > Personal access tokens
   - `repo`スコープを付与
3. 環境変数を設定:
```bash
OPAQUE_STORAGE_BACKEND=github
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=username/opaque-data
GITHUB_BRANCH=main
GITHUB_DATA_PATH=data
```

### Supabase Storage

Supabase無料プラン（500MB、50,000リクエスト/月）:

1. https://supabase.com でプロジェクト作成
2. テーブルを作成:
```sql
CREATE TABLE domains (id text primary key, data jsonb);
CREATE TABLE proposals (id text primary key, data jsonb);
CREATE TABLE tiles (id text primary key, data jsonb);
```
3. 環境変数を設定:
```bash
OPAQUE_STORAGE_BACKEND=supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJxxxxxxxx
```

### JSONBin Storage

シンプルなJSONストレージ（10,000リクエスト/月無料）:

1. https://jsonbin.io でアカウント作成
2. 新しいBinを作成（初期データ: `{"collections": {}}`）
3. 環境変数を設定:
```bash
OPAQUE_STORAGE_BACKEND=jsonbin
JSONBIN_API_KEY=$2b$xxxxxxxx
JSONBIN_BIN_ID=xxxxxxxxxxxxxxxx
```

### ストレージ比較

| バックエンド | 無料枠 | 特徴 |
|------------|-------|-----|
| Local | 無制限 | ローカル開発用 |
| GitHub | 無制限* | バージョン管理、透明性 |
| Supabase | 500MB | SQLクエリ、リアルタイム |
| JSONBin | 10K/月 | シンプル、セットアップ簡単 |

*プライベートリポジトリは制限あり

## トラブルシューティング

### HuggingFace Transformersの確認

```bash
# Transformersが正しくインストールされているか確認
python -c "from transformers import AutoModel; print('OK')"

# GPUが利用可能か確認
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, MPS: {torch.backends.mps.is_available()}')"
```

### モデルのダウンロードが遅い

```bash
# キャッシュディレクトリを確認
python -c "from transformers import TRANSFORMERS_CACHE; print(TRANSFORMERS_CACHE)"

# 軽量モデルを使用（7Bモデル）
# config.pyでデフォルトモデルを deepseek-r1-7b に変更
```

### メモリ不足エラー

```bash
# 32Bモデルには32GB以上のVRAM/RAMが推奨
# メモリが足りない場合:
# 1. 7Bモデルを使用 (models_config.json でデフォルト変更)
# 2. 4bit量子化を有効化 (config.pyで use_4bit_quantization: true)
# 3. GGUF形式の量子化モデルを使用
```

### データベースエラー

```bash
# データベースをリセット
rm sql_app.db
python backend/create_db.py
```

## API エンドポイント一覧

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| `/api/auth/signup` | POST | ユーザー登録 |
| `/api/auth/token` | POST | ログイン（トークン取得） |
| `/api/questions/` | POST | 質問を送信 |
| `/api/questions/ws/{session_id}` | WS | ストリーミング回答 |
| `/api/domains/` | GET | ドメイン一覧 |
| `/api/domains/{id}` | GET/PUT/DELETE | ドメイン操作 |
| `/api/models/` | GET/POST | モデル一覧/追加 |
| `/api/models/{id}` | GET/PUT/DELETE | モデル操作 |
| `/api/models/{id}/test` | POST | モデル接続テスト |
| `/api/proposals/` | GET/POST | 編集提案一覧/作成 |
| `/api/proposals/{id}/review` | PUT | 提案レビュー |
| `/health` | GET | ヘルスチェック |

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                     NullAI System                         │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React + TypeScript)                              │
│  ├── Authentication UI                                      │
│  ├── Chat Interface (REST/WebSocket)                       │
│  ├── Domain Editor                                          │
│  └── Model Management                                       │
├─────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                          │
│  ├── Auth API (JWT)                                         │
│  ├── Questions API                                          │
│  ├── Domains API                                            │
│  ├── Models API                                             │
│  └── Proposals API                                          │
├─────────────────────────────────────────────────────────────┤
│  NullAI Core                                              │
│  ├── ModelRouter (Multi-LLM Support)                        │
│  ├── ConfigManager                                          │
│  ├── DendriticMemorySpace (Tree-like Memory)               │
│  └── DB Enrichment CLI                                      │
├─────────────────────────────────────────────────────────────┤
│  Inference Engine                                           │
│  ├── IlmAthensEngine (Orchestrator)                        │
│  ├── SpatialEncodingEngine (Coordinate Mapping)            │
│  ├── Judge Layer (Alpha + Beta Lobe)                       │
│  └── NurseLogSystem (Continuous Learning)                  │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                 │
│  ├── IathDB (Compressed Knowledge Tiles)                   │
│  ├── SQLite/PostgreSQL (User Data)                         │
│  └── JSON Config Files                                      │
├─────────────────────────────────────────────────────────────┤
│  LLM Providers                                              │
│  ├── Ollama (Local)                                         │
│  ├── OpenAI API                                             │
│  ├── Anthropic API                                          │
│  └── Custom Endpoints                                       │
└─────────────────────────────────────────────────────────────┘
```

## ライセンス

MIT License
