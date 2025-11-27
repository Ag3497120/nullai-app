# NullAI クイックリファレンス

## システム起動

```bash
# 全サービス起動
./start_null_ai.sh

# 個別起動
./start_null_ai.sh backend   # バックエンドのみ
./start_null_ai.sh frontend  # フロントエンドのみ
./start_null_ai.sh stop      # 停止
./start_null_ai.sh status    # ステータス確認
```

## アクセスURL

| サービス | URL |
|---------|-----|
| フロントエンド | http://localhost:5173 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

## DB拡充コマンド

### LLM推論による拡充
```bash
python null_ai/db_enrichment_cli.py --domain medical --count 50
python null_ai/db_enrichment_cli.py --all --count 30
python null_ai/db_enrichment_cli.py --domain legal --model deepseek-r1-32b --count 20
```

### Web検索による拡充
```bash
python null_ai/db_enrichment_cli.py --domain medical --web-search --count 10
python null_ai/db_enrichment_cli.py --domain medical --web-search --query "糖尿病 最新治療法 2024"
```

### 確認コマンド
```bash
python null_ai/db_enrichment_cli.py --list-models
python null_ai/db_enrichment_cli.py --list-domains
python null_ai/db_enrichment_cli.py --list-search-providers
python null_ai/db_enrichment_cli.py --domain medical --preview
```

## クラウドDB設定

```bash
python null_ai/cloud_db_setup.py --provider supabase
python null_ai/cloud_db_setup.py --provider github --repo username/opaque-data
python null_ai/cloud_db_setup.py --provider jsonbin
```

## 主要な環境変数

```bash
# 基本
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///./sql_app.db

# HuggingFace（オプション - Inference APIを使う場合）
HF_API_KEY=hf_xxx

# ORCID認証
ORCID_CLIENT_ID=APP-xxx
ORCID_CLIENT_SECRET=xxx
ORCID_SANDBOX=true

# クラウドストレージ
OPAQUE_STORAGE_BACKEND=supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx

# Web検索
BRAVE_API_KEY=xxx
TAVILY_API_KEY=xxx
```

## サポートモデルプロバイダー

| プロバイダー | 説明 | GPU要否 | 備考 |
|------------|------|---------|------|
| **huggingface** | HuggingFace Transformers | 推奨 | ローカル推論（高品質） |
| **ollama** | Ollama | 不要 | ローカル推論サーバー（高速） |
| huggingface_api | Inference API | 不要 | リモート推論 |
| local | ローカルモデル | 推奨 | Transformers互換 |
| gguf | llama.cpp形式 | 不要 | 量子化モデル |

**注意**: OpenAI/Anthropic等の競合APIは利用規約上の理由からサポートされていません。

### Ollamaとの切り替え

NullAIはTransformersとOllamaの両方をサポートしています：

**Ollama使用時の利点:**
- ✅ 高速な推論（モデルが常駐）
- ✅ GPUなしでも高速動作
- ✅ メモリ効率が良い
- ✅ 簡単なモデル管理

**Transformers使用時の利点:**
- ✅ より高品質な出力
- ✅ モデルの細かい制御
- ✅ インターネット不要

### Ollama推論の使用方法

```bash
# 1. Ollamaをインストール・起動
# start_null_ai.shが自動起動します
# または手動: ollama serve

# 2. モデルをダウンロード
ollama pull llama3.1
ollama pull qwen2.5:7b
ollama pull deepseek-r1:7b
ollama pull mistral

# 3. Ollamaモデルでdb拡充
/Users/motonishikoudai/project_locate/venv/bin/python null_ai/db_enrichment_cli.py \
  --domain medical \
  --model ollama-llama3 \
  --count 10

# 4. 利用可能なOllamaモデル一覧
/Users/motonishikoudai/project_locate/venv/bin/python null_ai/db_enrichment_cli.py --list-models | grep Ollama
```

### プロバイダーの切り替え

環境変数またはCLIオプションで簡単に切り替え可能：

```bash
# Transformersを使用（デフォルト）
python null_ai/db_enrichment_cli.py --domain medical --count 10

# Ollamaを使用（高速）
python null_ai/db_enrichment_cli.py --domain medical --model ollama-llama3 --count 10

# 特定のOllamaモデルを使用
python null_ai/db_enrichment_cli.py --domain legal --model ollama-deepseek-r1 --count 20
```

## ユーザーロール

| ロール | 権限 |
|-------|-----|
| guest | 閲覧、質問 |
| viewer | + 提案閲覧 |
| editor | + 提案作成・レビュー |
| expert | + 認証マーク付き編集 |
| admin | + 全管理機能 |

## 認証マーク

| マーク | 説明 |
|-------|-----|
| none | 未検証 |
| community | コミュニティレビュー済み（青） |
| expert | 専門家編集（緑） |
| multi_expert | 複数専門家検証（金） |

## ドメイン一覧

| ID | 名前 |
|----|-----|
| medical | 医療・健康 |
| legal | 法律・法務 |
| economics | 経済・金融 |
| programming | プログラミング |
| general | 一般知識 |

## API エンドポイント

```
POST /api/auth/signup          # ユーザー登録
POST /api/auth/token           # ログイン
GET  /api/auth/orcid/authorize # ORCID認証開始

POST /api/questions/           # 質問送信
WS   /api/questions/ws/{id}    # ストリーミング

GET  /api/domains/             # ドメイン一覧
PUT  /api/domains/{id}         # ドメイン更新

GET  /api/proposals/           # 提案一覧
POST /api/proposals/           # 提案作成
PUT  /api/proposals/{id}/review # 提案レビュー

GET  /api/models/              # モデル一覧
POST /api/models/{id}/test     # モデルテスト

# Knowledge Base (DB) ダウンロード - 誰でも可能
GET  /api/knowledge/export/iath    # .iathファイルダウンロード
GET  /api/knowledge/export/json    # JSON形式でエクスポート
GET  /api/knowledge/export/package # 完全パッケージ (ZIP)

# モデル世代交代（倒木システム）
GET  /api/succession/status                  # 世代交代ステータス
POST /api/succession/trigger                 # 世代交代実行
POST /api/succession/create-standalone-package # DB付きパッケージ生成
GET  /api/succession/history/inference       # 推論履歴取得
GET  /api/succession/history/succession      # 世代交代履歴
GET  /api/succession/exports                 # エクスポートファイル一覧
GET  /api/succession/snapshots               # DBスナップショット一覧
POST /api/succession/snapshots/restore       # スナップショット復元
GET  /api/succession/stats                   # 統計情報
```

## DBダウンロード（自由な編集）

### 概要
**誰でも（ゲスト含む）**Knowledge Baseをダウンロードしてローカルで自由に編集できます。
エキスパート認証なしでも、ローカルで実験・カスタマイズが可能。

### 使用方法

```bash
# .iathファイルをダウンロード
curl http://localhost:8000/api/knowledge/export/iath -o knowledge.iath

# JSON形式でダウンロード（人間が読める）
curl http://localhost:8000/api/knowledge/export/json -o knowledge.json

# 完全パッケージ（DB + README + config）
curl http://localhost:8000/api/knowledge/export/package -o knowledge_package.zip
```

### ダウンロード後の利用

```bash
# ZIPを展開
unzip knowledge_package.zip

# ローカルで編集
vim knowledge_base.json

# NullAIにインポート
cp knowledge_base.iath /path/to/null_ai/ilm_athens_medical_db.iath
```

### メリット
- ✅ エキスパート認証不要
- ✅ 完全にオープン、自由に編集
- ✅ フォークして独自バージョンを作成
- ✅ オフラインで実験可能
- ✅ バージョン管理が容易

## モデル世代交代（倒木システム）

### 概要
推論履歴を自動保存し、高品質なデータが蓄積されたらトレーニングデータとしてエクスポート。
森林の倒木が次世代の栄養となるように、古いモデルの知識を新モデルに継承。

### 使用方法

```bash
# ステータス確認
curl http://localhost:8000/api/succession/status

# 世代交代実行（手動）
curl -X POST http://localhost:8000/api/succession/trigger \
  -H "Content-Type: application/json" \
  -d '{"min_confidence": 0.8}'

# 推論履歴確認
curl "http://localhost:8000/api/succession/history/inference?limit=10"

# 統計情報
curl http://localhost:8000/api/succession/stats
```

### エクスポート形式
- **JSONL** (ChatML/Instruction/Completion形式)
- **CSV** (表形式)
- **Parquet** (大規模データ用)
- **HuggingFace Datasets** (transformers連携)

### 自動トリガー
- 高品質推論（信頼度≥0.8）が1000件蓄積されると自動実行
- 推論結果は `inference_history/` に日別保存
- エクスポートデータは `training_data/` に保存
- DBスナップショットは `db_archives/` に世代管理

### スタンドアロンパッケージ生成

**DB付き完全パッケージ**を生成し、単体で使える推論エンジンを作成：

```bash
# スタンドアロンパッケージを生成
curl -X POST http://localhost:8000/api/succession/create-standalone-package \
  -H "Content-Type: application/json" \
  -d '{"min_confidence": 0.8}'

# 生成されたパッケージは succession_packages/ に保存
ls succession_packages/
# null_ai_model_gen1_20250125_123456.zip
```

### パッケージ内容

```
null_ai_model_gen1_*.zip
├── training_data/          # トレーニングデータ
│   ├── *.jsonl            # ChatML/Instruction形式
│   ├── *.csv              # CSV形式
│   ├── *.parquet          # Parquet形式
│   └── dataset_*/         # HuggingFace Datasets
├── knowledge_base/        # Knowledge Base（推論用DB）
│   ├── knowledge.iath     # IATH形式DB
│   └── db_stats.json      # DB統計
├── run_inference.py       # 推論実行スクリプト
├── config.json            # 設定ファイル
└── README.md              # 使い方ガイド
```

### パッケージの使い方

```bash
# 展開
unzip null_ai_model_gen1_*.zip
cd null_ai_model_gen1_*/

# 1. Knowledge Baseを使って推論
python run_inference.py --question "糖尿病の治療法は？"

# 2. ファインチューニング
# training_data/ のデータでモデルを訓練

# 3. ファインチューニング後のモデルで推論
python run_inference.py --model ./output/checkpoint-1000 --question "質問"
```

### 利点
- ✅ 完全に独立して動作
- ✅ トレーニングデータ + KB が一体化
- ✅ すぐに使える推論スクリプト付き
- ✅ 世代ごとにバージョン管理
- ✅ 他のプロジェクトで再利用可能

## 多言語対応

### サポート言語
- 🇯🇵 日本語
- 🇬🇧 English

### 言語切り替え
- フロントエンド右上の言語スイッチャーで切り替え
- ブラウザの言語設定を自動検出
- 選択した言語はlocalStorageに保存

## トラブルシューティング

```bash
# HuggingFaceモデルダウンロード確認
python -c "from transformers import AutoModel; print('OK')"

# GPU確認
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, MPS: {torch.backends.mps.is_available()}')"

# DB初期化
rm sql_app.db
python backend/create_db.py

# 依存関係インストール（HuggingFace対応）
pip install transformers torch accelerate
pip install llama-cpp-python  # GGUF使用時
pip install -r requirements.txt
cd frontend && npm install
```

## ファイル構成

```
project_locate/
├── null_ai/         # コアフレームワーク
├── backend/           # FastAPI バックエンド
├── frontend/          # React フロントエンド
├── ilm_athens_engine/ # 推論エンジン
├── generated_tiles/   # 生成された知識タイル
├── enrichment_output/ # DB拡充結果
└── documentation/     # ドキュメント
```
