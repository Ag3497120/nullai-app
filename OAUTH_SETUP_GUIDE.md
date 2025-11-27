# NullAI 完全認証システムセットアップガイド

このガイドでは、Google OAuth2認証、ORCID専門家認証、ゲストアクセス、マルチテナントワークスペース機能の完全なセットアップ方法を説明します。

## 📋 実装済み機能

✅ **Google OAuth2認証** - Googleアカウントでログイン  
✅ **ORCID認証** - 専門家認証（自動的にexpertステータス付与）  
✅ **ゲストアクセス** - ログイン不要でDBを自由に操作  
✅ **マルチテナントワークスペース** - ユーザーごとに独立したDB環境  
✅ **権限管理システム** - 細かい権限制御  
✅ **完全なエラーハンドリング** - すべてのエラーケースに対応  

---

## ステップ1: データベースのセットアップ

### 1-1. データベースを初期化

```bash
# プロジェクトルートで実行
python init_db.py
```

これにより以下のテーブルが作成されます:
- `users` - ユーザー情報（Google/ORCID/ローカル認証対応）
- `workspaces` - ワークスペース（マルチテナントDB）
- `workspace_members` - ワークスペースメンバー管理
- `oauth_states` - OAuth認証の一時トークン

---

## ステップ2: Google OAuth2の設定

### 2-1. Google Cloud Consoleでプロジェクトを作成

1. **Google Cloud Console**にアクセス: https://console.cloud.google.com/
2. 新しいプロジェクトを作成または既存プロジェクトを選択
3. **APIとサービス** → **認証情報** に移動

### 2-2. OAuth 2.0クライアントIDを作成

1. 「**認証情報を作成**」→「**OAuth クライアント ID**」をクリック
2. アプリケーションの種類: **ウェブ アプリケーション**
3. 名前: `NullAI Web App`
4. **承認済みのリダイレクト URI**に追加:
   ```
   http://localhost:8000/api/oauth/google/callback
   ```
   本番環境用:
   ```
   https://your-domain.com/api/oauth/google/callback
   ```
5. **作成**をクリック

### 2-3. クライアントIDとシークレットをコピー

表示される以下の情報をコピー:
- **クライアント ID**: `xxxxx.apps.googleusercontent.com`
- **クライアント シークレット**: `GOCSPX-xxxxx`

### 2-4. .envファイルに設定

```bash
# .envファイルを作成
cp .env.example .env

# .envファイルを編集
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/oauth/google/callback
```

---

## ステップ3: ORCID認証の設定

### 3-1. ORCIDアカウントを作成

1. **ORCID**にアクセス: https://orcid.org/
2. アカウントを作成（既にある場合はログイン）

### 3-2. ORCID Developer Toolsにアクセス

1. **Developer Tools**にアクセス: https://orcid.org/developer-tools
2. **Register for the free Public API**をクリック

### 3-3. アプリケーションを登録

1. **Application name**: `NullAI`
2. **Website URL**: `http://localhost:8000` （開発環境）
3. **Description**: `NullAI Knowledge System with Expert Verification`
4. **Redirect URIs**に追加:
   ```
   http://localhost:8000/api/oauth/orcid/callback
   ```

### 3-4. クライアントIDとシークレットをコピー

登録後に表示される以下の情報をコピー:
- **Client ID**: `APP-XXXXXXXXXXXX`
- **Client Secret**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

### 3-5. .envファイルに設定

```bash
ORCID_CLIENT_ID=APP-XXXXXXXXXXXX
ORCID_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ORCID_REDIRECT_URI=http://localhost:8000/api/oauth/orcid/callback
ORCID_SANDBOX=false  # 本番環境
```

**開発環境用（サンドボックス）**:
```bash
ORCID_SANDBOX=true  # サンドボックス環境を使用
```

サンドボックス用のアプリケーションは https://sandbox.orcid.org/developer-tools で登録します。

---

## ステップ4: アプリケーションを起動

### 4-1. 依存関係をインストール

```bash
# 仮想環境を作成（まだの場合）
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt
```

### 4-2. サーバーを起動

```bash
# 開発モード
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

サーバーが起動したら、以下にアクセス:
- **API ドキュメント**: http://localhost:8000/docs
- **ヘルスチェック**: http://localhost:8000/health

---

## ステップ5: 認証機能のテスト

### 5-1. Google OAuth2認証をテスト

ブラウザで以下にアクセス:
```
http://localhost:8000/api/oauth/google/login
```

Googleのログイン画面が表示され、認証後にトークンが発行されます。

### 5-2. ORCID認証をテスト

ブラウザで以下にアクセス:
```
http://localhost:8000/api/oauth/orcid/login
```

ORCIDのログイン画面が表示され、認証後に専門家ステータスが付与されます。

### 5-3. ゲストセッションを作成

```bash
curl -X POST http://localhost:8000/api/oauth/guest
```

レスポンス例:
```json
{
  "success": true,
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user_id": "guest_abc123",
  "username": "guest",
  "display_name": "Guest User",
  "is_expert": false,
  "provider": "guest",
  "message": "Guest session created successfully"
}
```

---

## ステップ6: ワークスペース機能の使用

### 6-1. 新しいワークスペースを作成

```bash
curl -X POST http://localhost:8000/api/workspaces/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Medical Research",
    "description": "Personal medical knowledge database",
    "is_public": false,
    "allow_guest_edit": true
  }'
```

### 6-2. ワークスペース一覧を取得

```bash
curl http://localhost:8000/api/workspaces/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 6-3. ワークスペースを公開設定に変更

```bash
curl -X PATCH http://localhost:8000/api/workspaces/{workspace_id} \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_public": true, "allow_guest_edit": true}'
```

---

## API エンドポイント一覧

### 認証関連

| エンドポイント | メソッド | 説明 |
|--------------|---------|------|
| `/api/oauth/status` | GET | 利用可能な認証方法を確認 |
| `/api/oauth/google/login` | GET | Google認証を開始 |
| `/api/oauth/google/callback` | GET | Googleコールバック |
| `/api/oauth/orcid/login` | GET | ORCID認証を開始 |
| `/api/oauth/orcid/callback` | GET | ORCIDコールバック |
| `/api/oauth/guest` | POST | ゲストセッションを作成 |

### ワークスペース関連

| エンドポイント | メソッド | 説明 |
|--------------|---------|------|
| `/api/workspaces/` | GET | ワークスペース一覧 |
| `/api/workspaces/` | POST | 新規ワークスペース作成 |
| `/api/workspaces/{id}` | GET | ワークスペース詳細 |
| `/api/workspaces/{id}` | PATCH | ワークスペース更新 |
| `/api/workspaces/{id}` | DELETE | ワークスペース削除 |
| `/api/workspaces/{id}/members` | GET | メンバー一覧 |

---

## トラブルシューティング

### 問題1: "Google authentication is not configured"

**原因**: Google OAuth2の環境変数が設定されていない

**解決策**:
1. `.env`ファイルに`GOOGLE_CLIENT_ID`と`GOOGLE_CLIENT_SECRET`が正しく設定されているか確認
2. サーバーを再起動

### 問題2: "Invalid or expired state token"

**原因**: OAuth認証フローが10分以上経過して期限切れ

**解決策**:
- 認証を最初からやり直す
- データベースの`oauth_states`テーブルをクリア

### 問題3: ORCIDのリダイレクトURLエラー

**原因**: ORCID Developer Toolsに登録したリダイレクトURIが一致していない

**解決策**:
1. ORCID Developer Toolsで登録したRedirect URIを確認
2. `.env`ファイルの`ORCID_REDIRECT_URI`と完全に一致させる
3. サンドボックス環境と本番環境の違いに注意

**重要**: ORCIDのRedirect URIは**完全一致**する必要があります:
- ❌ `http://localhost:8000/api/auth/orcid/callback` （旧エンドポイント）
- ✅ `http://localhost:8000/api/oauth/orcid/callback` （新エンドポイント）

### 問題4: データベーステーブルが見つからない

**原因**: データベースが初期化されていない

**解決策**:
```bash
python init_db.py
```

---

## セキュリティのベストプラクティス

### 本番環境での推奨設定

1. **SECRET_KEYを変更**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **HTTPSを使用**:
   - Redirect URIを`https://`に変更
   - Google/ORCIDの設定も更新

3. **CORS設定を制限**:
   ```bash
   CORS_ORIGINS=https://your-frontend-domain.com
   ```

4. **Rate Limitingを有効化**:
   ```bash
   RATE_LIMIT_ENABLED=true
   RATE_LIMIT_PER_MINUTE=60
   ```

5. **OAuthトークンの暗号化**:
   現在はプレーンテキストで保存されていますが、本番環境では暗号化を推奨

---

## 完了！

これで完全な認証システムとマルチテナントワークスペース機能が利用可能になりました。

**次のステップ**:
- フロントエンドにログインUIを実装
- ワークスペースの切り替えUIを追加
- 専門家専用機能を実装

サポートが必要な場合は、API ドキュメント（http://localhost:8000/docs）を参照してください。
