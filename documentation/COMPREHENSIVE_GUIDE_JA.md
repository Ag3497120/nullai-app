# NullAI 総合ガイド

## 目次

1. [システム概要](#1-システム概要)
2. [アーキテクチャ](#2-アーキテクチャ)
3. [セットアップ手順](#3-セットアップ手順)
4. [コマンドリファレンス](#4-コマンドリファレンス)
5. [API仕様](#5-api仕様)
6. [知識ベース管理](#6-知識ベース管理)
7. [認証システム](#7-認証システム)
8. [クラウドデプロイメント](#8-クラウドデプロイメント)
9. [トラブルシューティング](#9-トラブルシューティング)

---

## 1. システム概要

### 1.1 NullAIとは

NullAIは、**マルチドメイン対応の知識推論システム**です。以下の特徴を持ちます：

- **幻覚（ハルシネーション）低減**: 5層アーキテクチャによる検証システム
- **マルチドメイン対応**: 医療、法律、経済、プログラミング、一般知識
- **HuggingFace対応**: Transformers、Inference API、GGUF形式をサポート
- **専門家認証**: ORCID認証による専門家の編集認証マーク
- **サーバーレス対応**: GitHub/Supabase/JSONBinによる無料ストレージ

> **重要**: OpenAI/Anthropic/Ollama等の外部APIは利用規約上の理由から削除されました。NullAIはオープンソースモデルのみをサポートします。

### 1.2 主要コンポーネント

```
NullAI/
├── null_ai/           # コア設定・モデルルーター
├── backend/             # FastAPI バックエンドAPI
├── frontend/            # React TypeScript フロントエンド
├── ilm_athens_engine/   # 推論エンジン本体
└── 各種ユーティリティ    # エンコーダー、デコーダー等
```

### 1.3 推論パイプライン

```
質問入力
    ↓
[Layer 1] 空間エンコーディング - 質問をドメイン空間座標にマッピング
    ↓
[Layer 2] エピソードバインディング - 関連知識タイルの検索・結合
    ↓
[Layer 3] α-Lobe（生成）+ β-Lobe（検証）- 回答生成と妥当性検証
    ↓
[Layer 4] 修正フロー - 検証失敗時の自動修正
    ↓
[Layer 5] 状態管理 - 結果の保存と状態更新
    ↓
回答出力 + 信頼度スコア
```

---

## 2. アーキテクチャ

### 2.1 バックエンド構成

```
backend/
├── app/
│   ├── main.py              # FastAPIエントリーポイント
│   ├── config.py            # 環境設定
│   ├── api/
│   │   ├── questions.py     # 質問API（REST + WebSocket）
│   │   ├── auth.py          # 認証API（JWT）
│   │   ├── domains.py       # ドメイン管理API
│   │   ├── proposals.py     # 編集提案API
│   │   ├── models.py        # LLMモデル管理API
│   │   └── orcid_auth.py    # ORCID認証API
│   ├── middleware/
│   │   └── auth.py          # JWT認証ミドルウェア
│   ├── services/
│   │   └── inference_service.py  # 推論サービス
│   └── database/
│       ├── models.py        # SQLAlchemy ORM
│       └── session.py       # DBセッション
```

### 2.2 フロントエンド構成

```
frontend/src/
├── App.tsx                  # メインアプリ
├── pages/
│   ├── QuestionPage.tsx     # チャットUI
│   ├── LoginPage.tsx        # ログイン（ORCID/Email/Guest）
│   ├── SignupPage.tsx       # ユーザー登録
│   └── DomainEditorPage.tsx # ドメイン編集
├── components/
│   ├── QuestionInput.tsx    # 質問入力フォーム
│   ├── ResponseDisplay.tsx  # 回答表示
│   └── VerificationBadge.tsx # 認証バッジ
├── contexts/
│   └── AuthContext.tsx      # 認証状態管理
├── hooks/
│   └── useWebSocket.ts      # WebSocketフック
└── services/
    └── api.ts               # API クライアント
```

### 2.3 推論エンジン構成

```
ilm_athens_engine/
├── config.py                           # システム設定
├── model_manager.py                    # モデルライフサイクル管理
├── inference_engine_deepseek_integrated.py  # 統合推論エンジン
├── core/
│   ├── spatial_memory.py               # 空間メモリ（Layer 6）
│   ├── episodic_binding.py             # エピソードバインディング
│   ├── symbiotic_engine.py             # ツインエンジンシステム
│   ├── dendritic_memory.py             # 樹木型メモリ構造
│   └── nurse_log_system.py             # 継続学習システム
└── deepseek_integration/
    ├── hf_deepseek_engine.py           # HuggingFace統合
    └── deepseek_runner.py              # Ollama統合
```

### 2.4 データフロー

```
ユーザー → フロントエンド → バックエンドAPI
                              ↓
                        推論エンジン
                              ↓
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
         知識タイルDB    LLM推論        Web検索
         (IATH形式)    (DeepSeek等)   (DuckDuckGo等)
              ↓               ↓               ↓
              └───────────────┼───────────────┘
                              ↓
                        α-Lobe（生成）
                              ↓
                        β-Lobe（検証）
                              ↓
                    回答 + 信頼度 + 認証マーク
```

---

## 3. セットアップ手順

### 3.1 必要環境

- Python 3.10以上
- Node.js 18以上
- GPU（推奨: CUDA対応 または Apple Silicon）
- PostgreSQL（オプション、SQLiteでも動作）

#### 必要なPythonパッケージ（LLM関連）

```bash
# HuggingFace Transformers（必須）
pip install transformers torch accelerate

# GGUF形式を使用する場合
pip install llama-cpp-python
```

### 3.2 基本セットアップ

```bash
# 1. リポジトリをクローン（または既存ディレクトリへ移動）
cd project_locate

# 2. Python仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 依存パッケージのインストール
pip install -r requirements.txt

# 4. フロントエンド依存パッケージのインストール
cd frontend
npm install
cd ..

# 5. 環境変数の設定
cp .env.example .env  # または手動で作成
```

### 3.3 環境変数設定 (.env)

```bash
# ========== 基本設定 ==========
SECRET_KEY=your-secret-key-change-in-production
DEBUG=true
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ========== データベース ==========
DATABASE_URL=sqlite:///./sql_app.db
# PostgreSQLの場合:
# DATABASE_URL=postgresql://user:password@localhost:5432/null_ai

# ========== HuggingFace設定 ==========
# Inference APIを使用する場合（オプション）
# HF_API_KEY=hf_xxx

# ========== サポート対象外のLLM API ==========
# 以下のAPIは利用規約上の理由からサポートされていません：
# - OpenAI API (OPENAI_API_KEY)
# - Anthropic API (ANTHROPIC_API_KEY)
# - Ollama API (OLLAMA_URL)

# ========== ORCID認証（専門家認証機能）==========
# ORCID_CLIENT_ID=APP-XXXXXXXXX
# ORCID_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# ORCID_REDIRECT_URI=http://localhost:8000/api/auth/orcid/callback
# ORCID_SANDBOX=true  # 開発時はtrue

# ========== サーバーレスストレージ（オプション）==========
# OPAQUE_STORAGE_BACKEND=local  # local, github, supabase, jsonbin

# GitHub Storage
# GITHUB_TOKEN=ghp_xxxxxxxxxxxx
# GITHUB_REPO=username/opaque-data

# Supabase Storage
# SUPABASE_URL=https://xxxxx.supabase.co
# SUPABASE_ANON_KEY=eyJxxxxxxxx

# ========== Web検索（オプション）==========
# BRAVE_API_KEY=your-brave-api-key
# TAVILY_API_KEY=your-tavily-api-key
```

### 3.4 Ollamaセットアップ

```bash
# Ollamaのインストール（macOS）
brew install ollama

# Ollamaサービスの起動
ollama serve

# モデルのダウンロード（別ターミナル）
ollama pull deepseek-r1:32b  # メインモデル（32B推奨）
ollama pull deepseek-r1:14b  # 軽量版（RAMが少ない場合）
```

### 3.5 データベース初期化

```bash
# SQLiteデータベースの初期化
python backend/create_db.py

# 初期ドメインデータの投入
python null_ai/cloud_db_setup.py --provider local --init-data
```

### 3.6 システム起動

#### 方法A: 起動スクリプト使用（推奨）

```bash
# 全サービス起動
./start_null_ai.sh

# バックエンドのみ
./start_null_ai.sh backend

# フロントエンドのみ
./start_null_ai.sh frontend

# 停止
./start_null_ai.sh stop

# ステータス確認
./start_null_ai.sh status
```

#### 方法B: 個別起動（開発時）

```bash
# ターミナル1: バックエンド
source venv/bin/activate
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# ターミナル2: フロントエンド
cd frontend
npm run dev
```

#### 方法C: Docker Compose

```bash
docker-compose up -d
docker-compose logs -f
```

### 3.7 アクセス

| サービス | URL |
|---------|-----|
| フロントエンド | http://localhost:5173 |
| バックエンドAPI | http://localhost:8000 |
| API ドキュメント | http://localhost:8000/docs |
| Ollama | http://localhost:11434 |

---

## 4. コマンドリファレンス

### 4.1 DB拡充コマンド

#### 基本的な使い方

```bash
# ヘルプを表示
python null_ai/db_enrichment_cli.py --help

# 利用可能なモデル一覧
python null_ai/db_enrichment_cli.py --list-models

# 利用可能なドメイン一覧
python null_ai/db_enrichment_cli.py --list-domains

# 生成される質問をプレビュー（実行なし）
python null_ai/db_enrichment_cli.py --domain medical --preview --count 20
```

#### LLM推論によるDB拡充

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

#### Web検索によるDB拡充

```bash
# Web検索で最新情報を収集（DuckDuckGo使用、無料・キー不要）
python null_ai/db_enrichment_cli.py --domain medical --web-search --count 10

# 特定のクエリでWeb検索
python null_ai/db_enrichment_cli.py --domain medical --web-search \
    --query "最新の糖尿病治療法 2024"

# クエリファイルから検索
python null_ai/db_enrichment_cli.py --domain legal --web-search \
    --queries-file legal_queries.txt

# 利用可能な検索プロバイダーを確認
python null_ai/db_enrichment_cli.py --list-search-providers
```

### 4.2 知識タイル生成コマンド

```bash
# 単一トピックからタイル生成
python create_tile_from_topic.py --topic "心筋梗塞の治療法" --domain medical

# バッチ生成（トピックファイルから）
python batch_create_tiles.py --topics-file topics.txt --domain medical

# IATHファイルの検証
python compression_verifier.py --file generated_tiles/tile_xxx.iath
```

### 4.3 クラウドDB設定コマンド

```bash
# Supabaseセットアップ手順を表示
python null_ai/cloud_db_setup.py --provider supabase

# GitHubストレージセットアップ
python null_ai/cloud_db_setup.py --provider github --repo username/opaque-data

# JSONBinセットアップ
python null_ai/cloud_db_setup.py --provider jsonbin

# Supabaseに初期データ投入
python null_ai/cloud_db_setup.py --provider supabase --init-data
```

### 4.4 Web検索単独実行

```bash
# 医療ドメインで最新情報を検索
python null_ai/web_search_enrichment.py --domain medical --count 10

# 特定クエリで検索
python null_ai/web_search_enrichment.py --domain medical \
    --query "COVID-19 最新治療法 2024"

# 全ドメインで検索
python null_ai/web_search_enrichment.py --all-domains --count 5

# 検索プロバイダー一覧
python null_ai/web_search_enrichment.py --list-providers
```

### 4.5 テスト実行

```bash
# 基本テスト
python test_judge_basic.py

# 包括的テスト
python test_judge_comprehensive.py

# DeepSeek統合テスト
python test_deepseek_integration.py

# E2Eパイプラインテスト
python e2e_pipeline_test.py

# 最終統合テスト
python final_integration_test.py
```

---

## 5. API仕様

### 5.1 認証API

#### ユーザー登録
```http
POST /api/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
```

#### ログイン（JWTトークン取得）
```http
POST /api/auth/token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword
```

#### ORCID認証開始
```http
GET /api/auth/orcid/authorize?redirect_url=http://localhost:5173
```

### 5.2 質問API

#### 質問送信（REST）
```http
POST /api/questions/
Authorization: Bearer {token}
Content-Type: application/json

{
  "question": "糖尿病の最新治療法について教えてください",
  "domain_id": "medical",
  "session_id": null
}
```

#### レスポンス例
```json
{
  "session_id": "sess_abc123",
  "question": "糖尿病の最新治療法について教えてください",
  "response": "糖尿病の最新治療法には...",
  "confidence": 0.87,
  "memory_augmented": true,
  "thinking_steps": ["知識検索中...", "回答生成中...", "検証中..."]
}
```

#### WebSocketストリーミング
```javascript
const ws = new WebSocket('ws://localhost:8000/api/questions/ws/session_id');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type: 'thinking', 'response', 'complete', 'error'
};

ws.send(JSON.stringify({
  question: "質問内容",
  domain_id: "medical"
}));
```

### 5.3 ドメインAPI

#### ドメイン一覧取得（ゲストアクセス可）
```http
GET /api/domains/
```

#### 特定ドメイン取得
```http
GET /api/domains/medical
```

#### ドメイン更新（Editor以上）
```http
PUT /api/domains/medical
Authorization: Bearer {token}
Content-Type: application/json

{
  "domain_id": "medical",
  "name": "Medical",
  "description": "医療・健康に関する知識領域",
  "axes": [
    {"name": "診断", "description": "症状から疾患を特定", "keywords": ["症状", "検査"]}
  ]
}
```

### 5.4 編集提案API

#### 提案一覧取得（ゲストアクセス可）
```http
GET /api/proposals/?status=pending&domain_id=medical
```

#### 提案作成（認証必須）
```http
POST /api/proposals/
Authorization: Bearer {token}
Content-Type: application/json

{
  "proposal_type": "create",
  "domain_id": "medical",
  "title": "新しい治療法の追加",
  "description": "最新の糖尿病治療法について",
  "proposed_content": {...},
  "justification": "最新の研究結果に基づく"
}
```

#### 提案レビュー（Editor以上）
```http
PUT /api/proposals/{proposal_id}/review
Authorization: Bearer {token}
Content-Type: application/json

{
  "status": "approved",
  "reviewer_comment": "内容を確認しました",
  "validation_score": 0.9
}
```

### 5.5 モデル管理API

#### モデル一覧取得
```http
GET /api/models/?domain_id=medical
Authorization: Bearer {token}
```

#### モデル接続テスト
```http
POST /api/models/deepseek-r1-32b/test
Authorization: Bearer {token}
```

---

## 6. 知識ベース管理

### 6.1 知識タイル構造

```json
{
  "metadata": {
    "knowledge_id": "ktile-medical-20241124-001",
    "topic": "糖尿病の診断基準",
    "domain": "medical",
    "created_at": "2024-11-24T10:30:00Z",
    "source_type": "llm",
    "is_expert_verified": true,
    "expert_orcid_id": "0000-0001-2345-6789"
  },
  "content": {
    "question": "糖尿病の診断基準は何ですか？",
    "thinking_process": "診断基準について、HbA1c、空腹時血糖値...",
    "final_response": "糖尿病の診断基準は以下の通りです..."
  },
  "coordinates": {
    "medical_space": [45.2, 120.5, 30.0],
    "meta_space": [87.5, 92.0, 85.0]
  },
  "verification": {
    "alpha_score": 0.92,
    "beta_score": 0.88,
    "hallucination_risk": 0.05
  }
}
```

### 6.2 IATHファイル形式

NullAIは独自のバイナリ形式（`.iath`）を使用して知識タイルを保存します：

- **圧縮**: zstandard圧縮
- **ヘッダー**: ドメインコード、バージョン、タイムスタンプ
- **本体**: JSON形式の知識タイルデータ

```bash
# IATHファイルのデコード
python iath_decoder.py generated_tiles/tile_xxx.iath

# IATHファイルの作成
python iath_encoder.py --input tile_data.json --output tile.iath
```

### 6.3 樹木型メモリ構造（DendriticMemorySpace）

知識タイルは3次元円筒座標系で管理されます：

```
座標系:
- r (半径): 0-100 - 知識の具体性（中心=抽象、外側=具体）
- θ (角度): 0-360° - 知識のカテゴリ
- z (高さ): -50〜50 - 時間/重要度
```

知識検索時に、質問が座標にマッピングされ、近接する知識タイルが自動的に参照されます。

---

## 7. 認証システム

### 7.1 ユーザーロール

| ロール | 説明 | 権限 |
|-------|------|-----|
| guest | 未登録ユーザー | 閲覧、質問 |
| viewer | 登録ユーザー | + 提案の閲覧 |
| editor | 編集者 | + 提案の作成・レビュー |
| expert | ORCID認証済み専門家 | + 認証マーク付き編集 |
| admin | 管理者 | + 全管理機能 |

### 7.2 認証マークの種類

| マーク | 説明 | 表示 |
|-------|------|-----|
| none | 未検証 | なし |
| community | コミュニティレビュー済み | 青バッジ |
| expert | ORCID認証専門家による編集/レビュー | 緑バッジ |
| multi_expert | 複数の専門家による検証 | 金バッジ |

### 7.3 ORCID認証の設定

1. **ORCID開発者アカウントの作成**
   - https://orcid.org/developer-tools にアクセス
   - アプリケーション登録
   - Client IDとClient Secretを取得

2. **環境変数の設定**
```bash
ORCID_CLIENT_ID=APP-XXXXXXXXX
ORCID_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ORCID_REDIRECT_URI=http://localhost:8000/api/auth/orcid/callback
ORCID_SANDBOX=true  # 開発時はtrue
```

3. **認証フロー**
   - ユーザーが「Sign in with ORCID」をクリック
   - ORCIDの認証ページにリダイレクト
   - 認証後、コールバックURLにリダイレクト
   - JWTトークン発行（expert権限付与）

---

## 8. クラウドデプロイメント

### 8.1 サーバーレスストレージオプション

#### Supabase（推奨）

無料枠: 500MB、50,000リクエスト/月

```bash
# セットアップ手順を表示
python null_ai/cloud_db_setup.py --provider supabase

# 初期データ投入
python null_ai/cloud_db_setup.py --provider supabase --init-data
```

環境変数:
```bash
OPAQUE_STORAGE_BACKEND=supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJxxxxxxxx
```

#### GitHub Storage

無料枠: 無制限（パブリックリポジトリ）

```bash
# セットアップ手順を表示
python null_ai/cloud_db_setup.py --provider github --repo username/opaque-data
```

環境変数:
```bash
OPAQUE_STORAGE_BACKEND=github
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=username/opaque-data
GITHUB_BRANCH=main
GITHUB_DATA_PATH=data
```

#### JSONBin

無料枠: 10,000リクエスト/月

```bash
# セットアップ手順を表示
python null_ai/cloud_db_setup.py --provider jsonbin
```

環境変数:
```bash
OPAQUE_STORAGE_BACKEND=jsonbin
JSONBIN_API_KEY=$2b$xxxxxxxx
JSONBIN_BIN_ID=xxxxxxxxxxxxxxxx
```

### 8.2 ストレージ比較

| バックエンド | 無料枠 | 特徴 | 推奨用途 |
|------------|-------|-----|---------|
| Local | 無制限 | ファイルベース | 開発 |
| GitHub | 無制限* | バージョン管理、透明性 | オープンソースプロジェクト |
| Supabase | 500MB | SQLクエリ、リアルタイム | 本番環境 |
| JSONBin | 10K/月 | シンプル | 小規模プロジェクト |

*パブリックリポジトリの場合

### 8.3 フロントエンドデプロイ

#### Vercel（推奨）

```bash
# Vercel CLIインストール
npm i -g vercel

# デプロイ
cd frontend
vercel
```

#### Netlify

```bash
# ビルド
cd frontend
npm run build

# Netlifyにdistフォルダをアップロード
```

#### GitHub Pages

```bash
# gh-pagesパッケージをインストール
npm install gh-pages --save-dev

# package.jsonにスクリプト追加
# "deploy": "gh-pages -d dist"

# デプロイ
npm run build
npm run deploy
```

---

## 9. トラブルシューティング

### 9.1 Ollamaに接続できない

```bash
# Ollamaが起動しているか確認
curl http://localhost:11434/api/tags

# 起動していない場合
ollama serve

# モデルがダウンロードされているか確認
ollama list
```

### 9.2 モデルのダウンロードが遅い

```bash
# より軽量なモデルを使用
ollama pull deepseek-r1:14b  # 32Bの代わりに14B

# models_config.jsonでデフォルトモデルを変更
```

### 9.3 メモリ不足エラー

- 32Bモデルには32GB以上のRAMが推奨
- RAMが少ない場合は14Bモデルを使用
- Docker使用時はメモリ制限を確認

### 9.4 データベースエラー

```bash
# データベースをリセット
rm sql_app.db
python backend/create_db.py
```

### 9.5 ORCID認証が失敗する

- `ORCID_REDIRECT_URI`がORCIDの設定と一致しているか確認
- 開発時は`ORCID_SANDBOX=true`を設定
- Client IDとClient Secretが正しいか確認

### 9.6 Web検索が動作しない

```bash
# 検索プロバイダーの状態を確認
python null_ai/db_enrichment_cli.py --list-search-providers

# DuckDuckGoはAPIキー不要で動作するはず
# Brave/TavilyはAPIキーが必要
```

### 9.7 フロントエンドがAPIに接続できない

```bash
# CORSの設定を確認（backend/app/main.py）
# allow_origins=["*"] または具体的なオリジンを設定

# 環境変数を確認
# frontend/.env
VITE_API_URL=http://localhost:8000
```

---

## 付録A: ファイル一覧と役割

### コアモジュール

| ファイル | 役割 |
|---------|-----|
| `null_ai/config.py` | 設定管理（モデル、ドメイン） |
| `null_ai/model_router.py` | マルチLLMルーター |
| `null_ai/db_enrichment_cli.py` | DB拡充CLI |
| `null_ai/web_search_enrichment.py` | Web検索拡充 |
| `null_ai/serverless_storage.py` | クラウドストレージ |
| `null_ai/cloud_db_setup.py` | クラウドDB設定 |

### 推論エンジン

| ファイル | 役割 |
|---------|-----|
| `layer1_spatial_encoding.py` | 空間座標エンコーディング |
| `layer2_episodic_binding.py` | エピソードバインディング |
| `judge_alpha_lobe.py` | α-Lobe（回答生成） |
| `judge_beta_lobe_basic.py` | β-Lobe（基本検証） |
| `judge_beta_lobe_advanced.py` | β-Lobe（高度検証） |
| `judge_correction_flow.py` | 修正フロー |
| `hallucination_detector.py` | ハルシネーション検出 |

### データ処理

| ファイル | 役割 |
|---------|-----|
| `knowledge_tile_generator.py` | 知識タイル生成 |
| `iath_encoder.py` | IATHエンコーダー |
| `iath_decoder.py` | IATHデコーダー |
| `coordinate_mapper.py` | 座標マッピング |

---

## 付録B: 設定ファイル一覧

| ファイル | 用途 |
|---------|-----|
| `.env` | 環境変数（秘密情報） |
| `domain_schemas.json` | ドメイン定義 |
| `medical_space_axes_definition.json` | 医療ドメイン座標軸 |
| `legal_space_axes_definition.json` | 法律ドメイン座標軸 |
| `cardiology_ontology.json` | 循環器オントロジー |
| `legal_ontology.json` | 法律オントロジー |
| `docker-compose.yml` | Dockerコンテナ設定 |

---

## 付録C: よく使うコマンド一覧

```bash
# ========== 起動・停止 ==========
./start_null_ai.sh              # 全サービス起動
./start_null_ai.sh stop         # 全サービス停止
./start_null_ai.sh status       # ステータス確認

# ========== DB拡充 ==========
python null_ai/db_enrichment_cli.py --domain medical --count 50
python null_ai/db_enrichment_cli.py --domain medical --web-search --count 10
python null_ai/db_enrichment_cli.py --all --count 30

# ========== 確認・一覧 ==========
python null_ai/db_enrichment_cli.py --list-models
python null_ai/db_enrichment_cli.py --list-domains
python null_ai/db_enrichment_cli.py --list-search-providers
python null_ai/db_enrichment_cli.py --domain medical --preview

# ========== クラウド設定 ==========
python null_ai/cloud_db_setup.py --provider supabase
python null_ai/cloud_db_setup.py --provider github --repo user/repo

# ========== テスト ==========
python test_judge_basic.py
python e2e_pipeline_test.py
```

---

*このドキュメントは NullAI v1.0.0 に基づいています。*
*最終更新: 2024年11月24日*
