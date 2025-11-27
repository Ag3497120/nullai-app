# NullAI デプロイメントガイド

## 推奨構成: HuggingFace Spaces + Vercel（完全無料）

この構成は最もコスト効率が高く、世界中からアクセス可能です。

```
┌─────────────────┐      ┌────────────────────┐
│    Vercel       │      │  HuggingFace       │
│  (Frontend)     │─────▶│  Spaces (Backend)  │
│  - React/Vite   │      │  - Gradio API      │
│  - 無料100GB/月  │      │  - 無料GPU/CPU     │
└─────────────────┘      │  - 推論エンジン     │
                         └────────────────────┘
```

---

## 方法1: HuggingFace Spaces（最も簡単・推奨）

### ステップ1: HuggingFace アカウント作成
1. https://huggingface.co にアクセス
2. アカウントを作成（無料）

### ステップ2: Spaceを作成
```bash
# HuggingFace CLIをインストール
pip install huggingface_hub

# ログイン
huggingface-cli login

# Spaceを作成（Gradio SDK）
cd deployment/huggingface_space
huggingface-cli repo create null-ai --type space --space-sdk gradio
```

### ステップ3: ファイルをアップロード
```bash
# Gitでクローン
git clone https://huggingface.co/spaces/YOUR_USERNAME/null-ai
cd null-ai

# ファイルをコピー
cp ../deployment/huggingface_space/* .

# プッシュ
git add .
git commit -m "Initial deployment"
git push
```

### ステップ4: 環境変数設定（オプション）
HuggingFace SpacesのSettings → Variables で設定:
- `HF_TOKEN`: HuggingFaceトークン（プライベートモデル用）

**URL**: `https://huggingface.co/spaces/YOUR_USERNAME/null-ai`

---

## 方法2: Vercel + HuggingFace API（フロントエンド分離）

### ステップ1: Vercelにデプロイ
```bash
# Vercel CLIをインストール
npm i -g vercel

# フロントエンドディレクトリへ移動
cd frontend

# デプロイ
vercel

# 本番デプロイ
vercel --prod
```

### ステップ2: 環境変数設定
Vercelダッシュボードで設定:
```
VITE_API_URL=https://YOUR_USERNAME-null-ai.hf.space
```

---

## 方法3: Cloudflare Pages + Workers（高速・完全無料）

### ステップ1: フロントエンドをPages にデプロイ
```bash
# Wrangler CLIをインストール
npm i -g wrangler

# ビルド
cd frontend
npm run build

# デプロイ
wrangler pages deploy dist --project-name null-ai
```

### ステップ2: APIプロキシWorker
```javascript
// workers/api-proxy.js
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/')) {
      const hfUrl = `https://YOUR_USERNAME-null-ai.hf.space${url.pathname}`;
      return fetch(hfUrl, {
        method: request.method,
        headers: request.headers,
        body: request.body
      });
    }
    return fetch(request);
  }
};
```

---

## 方法4: Railway（バックエンド完全版）

GPUなしでCPU推論が可能な軽量版：

### ステップ1: Railwayアカウント作成
https://railway.app

### ステップ2: GitHubリポジトリを接続
```bash
# railway.jsonを作成
{
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "startCommand": "uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT"
  }
}
```

### 無料枠
- 月額$5クレジット（無料）
- 500時間の実行時間

---

## コスト比較

| サービス | 無料枠 | 超過料金 | GPU |
|---------|--------|----------|-----|
| HuggingFace Spaces | 無制限（CPU） | $0.06/hr (GPU) | ✓ |
| Vercel | 100GB/月 | $20/100GB | ✗ |
| Cloudflare | 10万リクエスト/日 | $0.50/100万 | ✗ |
| Railway | $5/月 | $0.000463/min | ✗ |

---

## 推奨設定

### 小規模（個人/デモ）
- **HuggingFace Spaces** のみ
- コスト: 完全無料
- 制限: 同時接続数に制限あり

### 中規模（チーム/研究）
- **Vercel** (フロントエンド) + **HuggingFace Spaces** (推論)
- コスト: 無料〜$20/月
- 利点: 高速なフロントエンド配信

### 大規模（本番）
- **Cloudflare Pages/Workers** + **HuggingFace Inference Endpoints**
- コスト: $50〜/月
- 利点: エンタープライズレベルの信頼性

---

## クイックスタート（最速デプロイ）

```bash
# 1. HuggingFace Spacesに直接デプロイ
cd deployment/huggingface_space

# 2. HuggingFaceにログイン
huggingface-cli login

# 3. Spaceを作成してプッシュ
huggingface-cli repo create null-ai --type space --space-sdk gradio
git init
git remote add origin https://huggingface.co/spaces/YOUR_USERNAME/null-ai
git add .
git commit -m "Deploy NullAI"
git push -u origin main

# 完了！ https://huggingface.co/spaces/YOUR_USERNAME/null-ai でアクセス可能
```

---

## トラブルシューティング

### モデルのロードが遅い
- 7Bモデルを使用（32Bは重い）
- HuggingFace Inference APIを使用

### メモリ不足
- 量子化モデル（GGUF）を使用
- `load_in_4bit=True` オプション

### CORS エラー
- Vercelの `vercel.json` でリライトルールを確認
- HuggingFace SpacesはデフォルトでCORS許可
