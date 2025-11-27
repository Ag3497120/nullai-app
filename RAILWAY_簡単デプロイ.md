# 🚀 Railway.app 超簡単デプロイ手順

## なぜRailway？

✅ **最も簡単** - ボタン数回でデプロイ完了
✅ **無料枠あり** - $5/月の無料クレジット
✅ **GitHubと自動連携** - プッシュするだけで自動デプロイ
✅ **設定ほぼ不要** - 自動検出してくれる

---

## 🎯 たった3ステップでデプロイ完了！

### ステップ1: GitHubにプッシュ（1分）

```bash
# まだプッシュしていない場合のみ実行
git push -u origin main
```

### ステップ2: Railway.appでデプロイ（2分）

1. **Railway.app**にアクセス: https://railway.app/
2. 「**Start a New Project**」をクリック
3. 「**Deploy from GitHub repo**」を選択
4. GitHubアカウントで連携（初回のみ）
5. リポジトリ `nullai-app` を選択
6. **自動的にデプロイが開始されます！**

### ステップ3: 環境変数を設定（1分）

デプロイが始まったら、左側のメニューから「**Variables**」をクリック：

```
APP_ENV=production
DEMO_MODE=true
ENABLE_INFERENCE=false
CORS_ORIGINS=*
SECRET_KEY=ランダムな文字列
```

**SECRET_KEY生成：**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

生成された文字列をコピーして `SECRET_KEY` に設定

---

## ✅ 完了！

数分後、デプロイが完了します。

**アプリURL：**
- Railwayの画面で「**Settings**」→「**Domains**」
- 「**Generate Domain**」をクリック
- `https://nullai-app-production.up.railway.app` のようなURLが発行されます

このURLをブラウザで開けば、あなたのアプリが動いています！

---

## 💡 便利な機能

### 自動デプロイ

GitHubにプッシュすると自動的に再デプロイされます：

```bash
git add .
git commit -m "Update features"
git push
# → 自動的に再デプロイ！
```

### ログの確認

Railway画面の「**Deployments**」→最新のデプロイをクリック→「**View Logs**」

### ドメインのカスタマイズ

「**Settings**」→「**Domains**」→「**Custom Domain**」で独自ドメインを設定可能

---

## 🆓 料金

- **無料枠**: $5/月のクレジット（約500時間稼働可能）
- **有料プラン**: $5/月〜（使った分だけ課金）

小規模なデモなら無料枠で十分です！

---

## 🔧 トラブルシューティング

### ビルドが失敗する

1. Railway画面の「**Deployments**」でログを確認
2. エラーメッセージを確認して修正

### 動かない

1. 「**Variables**」で環境変数が正しく設定されているか確認
2. 「**Settings**」→「**Healthcheck Path**」が `/health` になっているか確認

---

## 🎉 これで完了です！

Railway.appは最もシンプルなデプロイ方法の一つです。
GitHubにプッシュして、Railwayで選ぶだけ！

**何か問題があれば、Railwayのログを確認してください。**
