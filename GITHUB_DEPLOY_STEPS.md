# GitHubへのプッシュとデプロイ手順

## ステップ1: GitHubリポジトリを作成

1. **GitHub.com**にアクセス: https://github.com/new
2. リポジトリ名を入力: 例 `nullai-app`
3. Public または Private を選択
4. **「Create repository」をクリック**

## ステップ2: リモートリポジトリを設定してプッシュ

GitHubでリポジトリを作成したら、以下のコマンドを実行:

```bash
# リモートリポジトリを追加（YOUR_USERNAMEを自分のユーザー名に変更）
git remote add origin https://github.com/YOUR_USERNAME/nullai-app.git

# ブランチ名を確認
git branch

# mainブランチにリネーム（必要な場合）
git branch -M main

# GitHubにプッシュ
git push -u origin main
```

## ステップ3: Renderでバックエンドをデプロイ

1. **Render**にアクセス: https://dashboard.render.com
2. 「**New +**」→「**Web Service**」をクリック
3. 「**Connect GitHub**」または「**Connect GitLab**」
4. 先ほど作成したリポジトリを選択

### Renderの設定:

| 項目 | 値 |
|------|-----|
| **Name** | `nullai-backend` |
| **Region** | `Oregon (US West)` |
| **Branch** | `main` |
| **Root Directory** | `.` (空欄でOK) |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.production.txt` |
| **Start Command** | `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | **Free** |

### 環境変数を設定:

「Environment」タブで以下を追加:

```
APP_ENV=production
DEMO_MODE=true
ENABLE_INFERENCE=false
CORS_ORIGINS=*
SECRET_KEY=(ランダムな文字列を生成)
```

SECRET_KEYの生成:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

5. **「Create Web Service」をクリック**

デプロイが完了すると、URLが表示されます:
```
https://nullai-backend.onrender.com
```
**このURLをメモしてください！**

## ステップ4: Vercelでフロントエンドをデプロイ

1. **Vercel**にアクセス: https://vercel.com
2. 「**Add New...**」→「**Project**」をクリック
3. GitHubリポジトリをインポート
4. 同じリポジトリを選択

### Vercelの設定:

| 項目 | 値 |
|------|-----|
| **Framework Preset** | `Vite` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |

### 環境変数を設定:

```
VITE_API_URL=https://nullai-backend.onrender.com
```
（ステップ3でメモしたRenderのURLを使用）

5. **「Deploy」をクリック**

デプロイが完了すると、URLが表示されます:
```
https://nullai-xxxxx.vercel.app
```

## ✅ 完了！

これであなたのNullAIアプリケーションがライブになりました！

- **フロントエンド**: https://nullai-xxxxx.vercel.app
- **バックエンドAPI**: https://nullai-backend.onrender.com
- **APIドキュメント**: https://nullai-backend.onrender.com/docs

## 次のステップ（オプション）

### Google OAuth2の設定

1. Google Cloud Consoleで承認済みリダイレクトURIを更新:
   ```
   https://nullai-backend.onrender.com/api/oauth/google/callback
   ```

2. Renderの環境変数に追加:
   ```
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-secret
   GOOGLE_REDIRECT_URI=https://nullai-backend.onrender.com/api/oauth/google/callback
   ```

### ORCID認証の設定

1. ORCID Developer Toolsでリダイレク トURIを更新:
   ```
   https://nullai-backend.onrender.com/api/oauth/orcid/callback
   ```

2. Renderの環境変数に追加:
   ```
   ORCID_CLIENT_ID=APP-XXXXXXXXXXXX
   ORCID_CLIENT_SECRET=your-secret
   ORCID_REDIRECT_URI=https://nullai-backend.onrender.com/api/oauth/orcid/callback
   ```

## トラブルシューティング

### Renderのデプロイが失敗する

- ログを確認: Renderダッシュボード → Logs
- ビルドコマンドが正しいか確認
- Pythonバージョンが対応しているか確認

### Vercelのビルドが失敗する

- Root Directoryが `frontend` になっているか確認
- package.jsonがfrontendディレクトリにあるか確認

### CORS エラー

- Renderの環境変数で `CORS_ORIGINS=*` が設定されているか確認
- または特定のドメインを指定: `CORS_ORIGINS=https://nullai-xxxxx.vercel.app`
