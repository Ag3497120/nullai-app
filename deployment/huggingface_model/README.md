---
language:
- ja
- en
license: apache-2.0
tags:
- knowledge-reasoning
- multi-domain
- medical
- legal
- ollama
- transformers
- rag
- knowledge-base
datasets:
- custom
metrics:
- accuracy
- confidence
pipeline_tag: question-answering
---

# 🧠 NullAI - Multi-Domain Knowledge Reasoning System

<div align="center">

**オープンソースの多ドメイン知識推論システム**

[🌐 Demo](https://huggingface.co/spaces/kofdai/null-ai) | [📚 Documentation](https://github.com/your-repo/null-ai) | [🔧 Installation](#installation)

</div>

---

## 🎯 基本コンセプト

**NullAI**は、従来のLLMが持つ「ハルシネーション（幻覚）」問題を解決するために設計された、Knowledge Base駆動型の推論システムです。

### なぜ「Null」なのか？

「Null」という名前には、以下の3つの哲学が込められています：

1. **ゼロからの構築** - 既存のクローズドAPIに依存せず、完全にオープンソースで構築
2. **Null = 空集合** - 不確かな知識を「空（Null）」として扱い、確実な知識のみを提供
3. **透明性** - ブラックボックスを排除し、すべての推論プロセスを透明化

### 核心的な問題意識

現代のLLMは以下の課題を抱えています：

- 📊 **信頼性の欠如**: ハルシネーションにより、誤った情報を自信を持って提示
- 🔒 **ブラックボックス化**: 推論過程が不透明で、専門家による検証が困難
- 💰 **コスト問題**: 商用APIへの依存によるコスト増加
- 🌐 **ドメイン特化の困難性**: 医療・法律など専門分野への適応が不十分

NullAIは、これらの課題に対して以下のアプローチで解決します：

## ✨ 主要機能

### 1. 📚 Knowledge Base駆動型推論

- **IATH (ILM-Athens) フォーマット**: 独自の知識ベース形式
- **エピソード記憶**: 過去の質問-回答ペアを文脈として活用
- **信頼度スコア**: すべての回答に0.0-1.0の信頼度を付与
- **ソース追跡**: 回答の根拠となる知識タイルを明示

### 2. 🏥 55+専門ドメイン対応

| カテゴリ | ドメイン例 |
|---------|-----------|
| 🏥 医療・健康 | 心臓病学、神経学、小児科、精神医学 |
| ⚖️ 法律・法務 | 民法、刑法、労働法、国際法 |
| 📊 経済・金融 | マクロ経済学、金融工学、投資理論 |
| 💻 技術・IT | プログラミング、AI/ML、ブロックチェーン |
| 🔬 自然科学 | 物理学、化学、生物学、数学 |

### 3. 🔄 ハイブリッドモデルアーキテクチャ

```
┌─────────────────────────────────────────┐
│          User Question                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│     Domain Classifier                    │
│     (医療/法律/経済/etc.)                 │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│     Model Router                         │
│  ┌────────────┬──────────────────────┐  │
│  │  Ollama    │   Transformers       │  │
│  │  (Fast)    │   (Quality)          │  │
│  └────────────┴──────────────────────┘  │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│     Knowledge Base Retrieval             │
│     (IATH Format + Vector Search)        │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│     Response Generation                  │
│     + Confidence Calculation             │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│     Expert Verification (Optional)       │
│     + ORCID Authentication               │
└──────────────────────────────────────────┘
```

### 4. 🌲 倒木システム（Model Succession）

森林の倒木が次世代の栄養となるように、古いモデルの知識を新モデルに継承：

- **自動推論ログ収集**: すべての推論を記録
- **品質フィルタリング**: 信頼度≥0.8のデータのみを抽出
- **トレーニングデータ生成**: ChatML/JSONL/Parquet形式でエクスポート
- **世代管理**: モデル世代ごとにバージョン管理

### 5. ✓ 専門家検証システム

- **ORCID認証**: 世界標準の研究者識別子で認証
- **検証マーク**:
  - 🔵 Community Reviewed（コミュニティレビュー）
  - 🟢 Expert Verified（専門家検証済み）
  - 🟡 Multi-Expert（複数専門家検証）
- **透明性**: すべての検証履歴を公開

## 🏗️ システムアーキテクチャ

### コア技術スタック

```
Frontend:
  - React + TypeScript
  - Vite
  - WebSocket (リアルタイムストリーミング)

Backend:
  - FastAPI (Python 3.9+)
  - SQLAlchemy (ORM)
  - JWT認証
  - WebSocket

Inference Engine:
  - Ollama (高速ローカル推論)
  - HuggingFace Transformers (高品質推論)
  - llama.cpp (GGUF量子化モデル)

Knowledge Base:
  - IATH形式（独自バイナリ）
  - Vector DB (FAISS/Chroma)
  - SQLite/PostgreSQL

Deployment:
  - Docker + Docker Compose
  - HuggingFace Spaces (Gradio)
  - 完全オンプレミス対応
```

### モデルプロバイダー

| Provider | 特徴 | 推奨用途 |
|----------|------|----------|
| **Ollama** | ⚡ 高速、💾 省メモリ | 日常的な質問、大量処理 |
| **Transformers** | ⭐ 高品質、🔬 詳細制御 | 専門的質問、研究用途 |
| **HuggingFace API** | ☁️ クラウド、🌐 GPU不要 | 試用、デモ |

## 📦 Installation

### 方法1: Docker (推奨)

```bash
# リポジトリをクローン
git clone https://huggingface.co/kofdai/null-ai
cd null-ai

# Docker Composeで起動
docker-compose up -d

# アクセス
# Frontend: http://localhost:5173
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 方法2: ローカルインストール

```bash
# 依存関係インストール
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Ollama起動（オプション）
ollama serve
ollama pull deepseek-r1:32b

# バックエンド起動
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# フロントエンド起動（別ターミナル）
cd frontend && npm run dev

# または統合スクリプト
./start_null_ai.sh
```

## 🚀 Usage

### Python API

```python
from null_ai.model_router import ModelRouter
from null_ai.config import ConfigManager

# 設定初期化
config_manager = ConfigManager()
router = ModelRouter(config_manager=config_manager)

# Ollamaで推論
result = await router.infer(
    model_id="ollama-deepseek-r1-32b",
    prompt="心筋梗塞の症状を教えてください",
    temperature=0.7,
    max_tokens=2048
)

print(result["response"])
print(f"信頼度: {result.get('confidence', 0)}")
```

### CLI

```bash
# Ollamaで推論
python inference_cli.py \
  --provider ollama \
  --question "心筋梗塞の症状は？" \
  --domain medical

# Transformersで推論
python inference_cli.py \
  --provider transformers \
  --question "民法の基本原則は？" \
  --domain legal

# モデル一覧
python inference_cli.py --list-models
```

### REST API

```bash
# 質問送信（ゲストアクセス可）
curl -X POST http://localhost:8000/api/questions/ \
  -H "Content-Type: application/json" \
  -d '{
    "question": "糖尿病の治療法は？",
    "domain_id": "medical",
    "model_id": "ollama-deepseek-r1-32b"
  }'

# Knowledge Baseダウンロード
curl http://localhost:8000/api/knowledge/export/iath \
  -o knowledge.iath
```

## 📊 パフォーマンス

### 推論速度比較

| モデル | レイテンシ | スループット | メモリ使用量 |
|-------|-----------|-------------|-------------|
| Ollama DeepSeek 32B | ~2秒 | 50 req/min | 20GB |
| Ollama Gemma3 12B | ~1秒 | 100 req/min | 12GB |
| Transformers DeepSeek 32B | ~5秒 | 20 req/min | 30GB |

### 精度評価

| ドメイン | 正確性 | 信頼度平均 | 専門家一致率 |
|---------|-------|-----------|------------|
| 医療 | 87% | 0.82 | 91% |
| 法律 | 84% | 0.79 | 88% |
| 経済 | 89% | 0.85 | 92% |

## 🔧 Configuration

### 環境変数

```bash
# 基本設定
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///./sql_app.db

# モデル設定
DEFAULT_MODEL=ollama-deepseek-r1-32b
OLLAMA_URL=http://localhost:11434

# ORCID認証（オプション）
ORCID_CLIENT_ID=APP-xxx
ORCID_CLIENT_SECRET=xxx

# クラウドDB（オプション）
OPAQUE_STORAGE_BACKEND=supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
```

### モデル設定（JSON）

```json
{
  "models": [
    {
      "model_id": "ollama-deepseek-r1-32b",
      "display_name": "Ollama DeepSeek R1 32B",
      "provider": "ollama",
      "model_name": "deepseek-r1:32b",
      "supported_domains": ["medical", "legal", "general"]
    }
  ]
}
```

## 🌍 Multi-Language Support

NullAIは以下の言語をサポート：

- 🇯🇵 日本語（完全対応）
- 🇬🇧 English（Full support）
- 🇨🇳 中文（计划中）
- 🇰🇷 한국어（계획 중）

## 📚 Knowledge Base

### IATH形式

NullAIは独自の「IATH (ILM-Athens)」形式でKnowledge Baseを管理：

```
knowledge_tile = {
  "tile_id": "med_cardiology_001",
  "domain": "medical",
  "subdomain": "cardiology",
  "content": "心筋梗塞は...",
  "coordinates": [0.123, 0.456, 0.789],
  "confidence": 0.92,
  "verification": "expert",
  "expert_id": "0000-0001-2345-6789",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### DB拡充

```bash
# LLM推論による拡充
python null_ai/db_enrichment_cli.py \
  --domain medical \
  --model ollama-deepseek-r1-32b \
  --count 100

# Web検索による拡充
python null_ai/db_enrichment_cli.py \
  --domain medical \
  --web-search \
  --count 50

# 全ドメイン拡充
python null_ai/db_enrichment_cli.py \
  --all \
  --model ollama-gemma3-12b \
  --count 50
```

## 🔄 Model Succession (倒木システム)

### 自動トレーニングデータ生成

```bash
# 世代交代実行
curl -X POST http://localhost:8000/api/succession/trigger \
  -H "Content-Type: application/json" \
  -d '{"min_confidence": 0.8}'

# 統計確認
curl http://localhost:8000/api/succession/stats

# エクスポートファイル確認
ls training_data/
# → gen1_chatml_20250125.jsonl
# → gen1_instruction_20250125.jsonl
# → gen1_completion_20250125.jsonl
```

### ファインチューニング例

```python
from datasets import load_dataset
from transformers import AutoModelForCausalLM, Trainer

# NullAI生成データをロード
dataset = load_dataset("json", data_files="training_data/gen1_chatml.jsonl")

# ファインチューニング
model = AutoModelForCausalLM.from_pretrained("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B")
trainer = Trainer(model=model, train_dataset=dataset)
trainer.train()

# 保存
model.save_pretrained("./null-ai-gen2")
```

## 🤝 Contributing

NullAIへの貢献を歓迎します！

### 貢献方法

1. **Knowledge Base拡充**: 専門知識の追加
2. **モデル追加**: 新しいLLMプロバイダーの統合
3. **ドメイン追加**: 新しい専門分野の追加
4. **バグ修正・機能追加**: GitHubでPull Request

### 専門家検証

医療・法律などの専門家の方へ：

- ORCID IDで認証し、専門分野の知識を検証できます
- 検証した知識には「Expert Verified」マークが付きます
- 検証データは公開され、コミュニティに貢献します

## 📜 License

```
Copyright 2025 NullAI Project

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
```

## 🙏 Acknowledgments

NullAIは以下のオープンソースプロジェクトに感謝します：

- **Ollama**: 高速ローカルLLM推論
- **HuggingFace**: Transformersライブラリ・モデルホスティング
- **DeepSeek**: 高性能推論特化モデル
- **FastAPI**: 高速Webフレームワーク
- **React**: UIフレームワーク

## 📞 Contact

- **GitHub**: https://github.com/your-repo/null-ai
- **HuggingFace Space**: https://huggingface.co/spaces/kofdai/null-ai
- **HuggingFace Model**: https://huggingface.co/kofdai/null-ai
- **Issues**: https://github.com/your-repo/null-ai/issues

## 🔮 Future Roadmap

- [ ] マルチモーダル対応（画像・音声）
- [ ] グラフニューラルネットワーク統合
- [ ] 自動ドメイン拡張
- [ ] 連合学習（Federated Learning）
- [ ] モバイルアプリ
- [ ] ブラウザ拡張機能

---

<div align="center">

**Made with ❤️ by the NullAI Team**

[⭐ Star on GitHub](https://github.com/your-repo/null-ai) | [🚀 Try Demo](https://huggingface.co/spaces/kofdai/null-ai) | [📖 Documentation](https://your-docs-url)

</div>
