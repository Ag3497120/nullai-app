# NullAI AWS Amplifyデプロイ手順

## 📋 前提条件

- AWSアカウント（無料）
- GitHubリポジトリ（既に作成済み）

---

## 手順1: AWS Amplify用の設定ファイルを作成

### 1-1. Amplify設定ファイル作成

```bash
# amplify.ymlをプロジェクトルートに作成
cat > amplify.yml << 'YAML'
version: 1
backend:
  phases:
    build:
      commands:
        - pip install -r requirements.production.txt
        - python init_db.py
    
frontend:
  phases:
    preBuild:
      commands:
        - cd frontend
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: frontend/dist
    files:
      - '**/*'
  cache:
    paths:
      - frontend/node_modules/**/*

YAML
```

### 1-2. バックエンド用のDockerfileを確認

`backend/Dockerfile` が既にあることを確認。なければ作成：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.production.txt .
RUN pip install --no-cache-dir -r requirements.production.txt

COPY backend/ ./backend/
COPY init_db.py .
COPY models_config.json .
COPY domains_config.json .

RUN python init_db.py

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 1-3. GitHubにプッシュ

```bash
git add amplify.yml backend/Dockerfile
git commit -m "Add AWS Amplify configuration"
git push origin main
```

---

## 手順2: AWS Amplifyでアプリを作成

### 2-1. AWS Amplifyコンソールにアクセス

1. **AWS Management Console**にログイン: https://console.aws.amazon.com/
2. 検索バーで「**Amplify**」と入力
3. 「**AWS Amplify**」を選択

### 2-2. 新しいアプリを作成

1. 「**Get Started**」→ 「**Amplify Hosting**」を選択
2. 「**GitHub**」を選択して「**Continue**」
3. GitHubアカウントを連携（初回のみ）
4. リポジトリ（`nullai-app`）とブランチ（`main`）を選択
5. 「**Next**」をクリック

### 2-3. ビルド設定

Amplifyが自動的に `amplify.yml` を検出します。

確認して「**Next**」をクリック

### 2-4. 環境変数を設定

「**Advanced settings**」を展開して環境変数を追加：

```
APP_ENV=production
DEMO_MODE=true
ENABLE_INFERENCE=false
CORS_ORIGINS=*
SECRET_KEY=ここにランダムな文字列を入力
```

SECRET_KEY生成：
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2-5. デプロイを開始

1. 設定を確認
2. 「**Save and deploy**」をクリック
3. デプロイが自動的に開始されます（5〜10分）

---

## 手順3: デプロイ完了を確認

### 3-1. デプロイ状況を確認

Amplifyコンソールで以下のフェーズが完了するのを待ちます：

1. ✅ Provision（プロビジョニング）
2. ✅ Build（ビルド）
3. ✅ Deploy（デプロイ）
4. ✅ Verify（検証）

### 3-2. アプリURLを確認

デプロイが完了すると、URLが表示されます：

```
https://main.xxxxx.amplifyapp.com
```

このURLをブラウザで開いて動作確認！

---

## オプション: バックエンドを別途App Runnerにデプロイ

Amplifyでフロントエンドのみをホストし、バックエンドは**AWS App Runner**で別途デプロイする方法：

### App Runner手順

1. **AWS App Runner**コンソールにアクセス
2. 「**Create service**」をクリック
3. 「**Source code repository**」→ GitHubを選択
4. リポジトリとブランチを選択
5. ビルド設定：
   ```
   Build command: pip install -r requirements.production.txt
   Start command: uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   Port: 8000
   ```
6. 環境変数を設定（Amplifyと同じ）
7. 「**Create & deploy**」

App RunnerのURLが発行されます：
```
https://xxxxx.us-west-2.awsapprunner.com
```

Amplifyの環境変数に追加：
```
VITE_API_URL=https://xxxxx.us-west-2.awsapprunner.com
```

---

## 💰 料金

### AWS Amplify 無料枠（12ヶ月）
- ビルド時間: 1000分/月
- データ転送: 15GB/月
- ホスティング: 5GB保存

### AWS App Runner
- 無料枠なし
- 最小構成: 約$5〜10/月

---

## 🎯 完成！

あなたのNullAIアプリがAWS上で動作しています！

**アクセス先:**
```
https://main.xxxxx.amplifyapp.com
```

### 自動デプロイ

GitHubにプッシュすると自動的に再デプロイされます：

```bash
git add .
git commit -m "Update features"
git push origin main
# → AWS Amplifyが自動的にビルド＆デプロイ
```

---

## 🔧 追加設定

### カスタムドメインの設定

1. Amplifyコンソール → 「**Domain management**」
2. 「**Add domain**」をクリック
3. 自分のドメインを入力
4. DNSレコードを設定（Amplifyが指示）

### HTTPS証明書

Amplifyが自動的にSSL証明書を発行します（無料）

---

## トラブルシューティング

### ビルドが失敗する

**確認:**
- `amplify.yml` が正しいか
- `requirements.production.txt` が存在するか
- ビルドログでエラーを確認

### バックエンドが動かない

**確認:**
- ポート8000が正しく設定されているか
- 環境変数が設定されているか
- ログを確認: App Runner → Logs

### CORSエラー

**解決:**
- バックエンドの環境変数に `CORS_ORIGINS=*` を追加
- または特定のドメイン: `CORS_ORIGINS=https://main.xxxxx.amplifyapp.com`

---

## 📚 関連ドキュメント

- AWS Amplify公式: https://docs.aws.amazon.com/amplify/
- AWS App Runner公式: https://docs.aws.amazon.com/apprunner/
