# Python 3.11をベースイメージとして使用
FROM python:3.11-slim

# 作業ディレクトリを /app に設定
WORKDIR /app

# 統合された依存関係をインストール
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# backendディレクトリ全体をコンテナの/app/backendにコピー
COPY backend ./backend

# ポート8000を公開
EXPOSE 8000

# サーバーを起動
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
