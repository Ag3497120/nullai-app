# NullAI 無料デプロイ手順書（推論機能なしデモ版）

このガイドでは、**Vercel（フロントエンド）+ Render（バックエンド）** を使用した完全無料デプロイ方法を説明します。

## ✅ この構成で動作する機能

- ✓ フロントエンドUI（完全機能）
- ✓ データベース操作（知識タイル管理）
- ✓ ドメイン管理
- ✓ ユーザー管理
- ✓ API エンドポイント
- ✗ AI推論機能（無効化）

---

## 📋 前提条件

1. GitHubアカウント
2. Vercelアカウント（無料）- https://vercel.com
3. Renderアカウント（無料）- https://render.com

---

## ステップ1: GitHubリポジトリの準備

### 1-1. このプロジェクトをGitHubにプッシュ

```bash
# まだGitリポジトリでない場合
git init
git add .
git commit -m "Initial commit for deployment"

# GitHubで新しいリポジトリを作成してから
git remote add origin https://github.com/YOUR_USERNAME/nullai.git
git branch -M main
git push -u origin main
```

---

## ステップ2: バックエンドをRenderにデプロイ

### 2-1. Renderにログイン

https://dashboard.render.com にアクセスしてログイン

### 2-2. 新しいWeb Serviceを作成

1. 「New +」→「Web Service」をクリック
2. GitHubリポジトリを接続
3. このプロジェクトのリポジトリを選択

### 2-3. 設定を入力

| 項目 | 値 |
|------|-----|
| Name | `nullai-backend` |
| Region | `Oregon (US West)` |
| Branch | `main` または `master` |
| Root Directory | `.` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.production.txt` |
| Start Command | `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | `Free` |

### 2-4. 環境変数を設定

「Environment」セクションで以下を追加：

```
APP_ENV=production
DEMO_MODE=true
ENABLE_INFERENCE=false
DATABASE_URL=$DATABASE_URL
SECRET_KEY=<ランダムな文字列を生成>
CORS_ORIGINS=*
```

**SECRET_KEYの生成方法：**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2-5. デプロイを実行

「Create Web Service」をクリック → 自動的にデプロイ開始

デプロイ完了後、URLが表示されます：
```
https://nullai-backend.onrender.com
```

**このURLをメモしておいてください！**

---

## ステップ3: フロントエンドをVercelにデプロイ

### 3-1. Vercelにログイン

https://vercel.com にアクセスしてログイン

### 3-2. 新しいプロジェクトを作成

1. 「Add New...」→「Project」をクリック
2. GitHubリポジトリをインポート
3. このプロジェクトのリポジトリを選択

### 3-3. 設定を入力

| 項目 | 値 |
|------|-----|
| Framework Preset | `Vite` |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |

### 3-4. 環境変数を設定

「Environment Variables」セクションで以下を追加：

```
VITE_API_URL=https://nullai-backend.onrender.com
```

（ステップ2-5でメモしたRenderのURLを使用）

### 3-5. デプロイを実行

「Deploy」をクリック → 自動的にビルド＆デプロイ

デプロイ完了後、URLが表示されます：
```
https://nullai-xxxxx.vercel.app
```

---

## ステップ4: 動作確認

### 4-1. フロントエンドにアクセス

Vercelから提供されたURL（`https://nullai-xxxxx.vercel.app`）にアクセス

### 4-2. APIヘルスチェック

```bash
curl https://nullai-backend.onrender.com/health
```

レスポンス：
```json
{"status":"ok","service":"ilm-athens-api"}
```

### 4-3. データベース確認

フロントエンドから：
- ドメイン一覧が表示されるか確認
- 知識タイル一覧が表示されるか確認

---

## 🚨 トラブルシューティング

### 問題1: Renderのデプロイが失敗する

**原因**: requirements.production.txt が見つからない

**解決策**:
```bash
# プロジェクトルートで実行
ls -la requirements.production.txt

# なければこのファイルを作成してコミット・プッシュ
git add requirements.production.txt
git commit -m "Add production requirements"
git push
```

### 問題2: フロントエンドからAPIに接続できない

**原因**: CORS設定またはAPI URLが間違っている

**解決策**:
1. Renderの環境変数で `CORS_ORIGINS=*` が設定されているか確認
2. Vercelの環境変数で `VITE_API_URL` が正しいRender URLになっているか確認
3. Vercelを再デプロイ

### 問題3: Renderのサービスがスリープする

**原因**: 無料プランは15分間アクセスがないとスリープ

**解決策**:
- 初回アクセス時は起動に30秒〜1分かかります（正常な動作）
- UptimeRobotなどの監視サービスで5分おきにpingを送る（オプション）

---

## 📊 無料枠の制限

### Vercel（フロントエンド）
- ✓ 帯域幅: 100GB/月
- ✓ ビルド時間: 6000分/月
- ✓ 自動HTTPS
- ✓ カスタムドメイン対応

### Render（バックエンド）
- ✓ 750時間/月の稼働時間
- ✓ PostgreSQL 90日間保持（オプション）
- ✓ 自動デプロイ
- ⚠️ 15分間アクセスなしでスリープ

---

## 🎯 次のステップ（オプション）

### カスタムドメインの設定

**Vercelでカスタムドメインを追加:**
1. Vercelダッシュボード → プロジェクト → Settings → Domains
2. ドメインを入力して追加
3. DNSレコードを設定

**Renderでカスタムドメインを追加:**
1. Renderダッシュボード → サービス → Settings → Custom Domains
2. ドメインを入力して追加
3. CNAMEレコードを設定

### PostgreSQLデータベースの追加（オプション）

現在はSQLiteを使用していますが、本格運用にはPostgreSQLを推奨：

1. Render → 「New +」→「PostgreSQL」
2. 無料プラン選択
3. データベース情報をコピー
4. バックエンドの環境変数 `DATABASE_URL` を更新

---

## 💡 コスト削減のヒント

1. **Renderのスリープを回避**: UptimeRobotで5分おきにpingを送る（無料）
2. **Cloudflareを前段に配置**: CDN+キャッシュで帯域幅削減（無料）
3. **画像最適化**: Vercel Image Optimizationを活用

---

## ✅ 完了！

これで完全無料でNullAIデモ版が公開されました！

- **フロントエンド**: https://nullai-xxxxx.vercel.app
- **バックエンドAPI**: https://nullai-backend.onrender.com
- **APIドキュメント**: https://nullai-backend.onrender.com/docs

推論機能が必要な場合は、別途GPUサーバーまたはHuggingFace Inference APIを統合してください。
