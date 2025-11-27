# --- ビルドステージ ---
FROM node:20-alpine AS build

WORKDIR /app

# 依存関係をコピーしてインストール
COPY frontend/package.json .
COPY frontend/package-lock.json .
RUN npm install

# アプリケーションのソースコードをコピー
COPY frontend/ .

# Reactアプリケーションをビルド
RUN npm run build

# --- サーブステージ ---
FROM nginx:1.25-alpine

# ビルドステージから静的ファイルをコピー
COPY --from=build /app/dist /usr/share/nginx/html

# nginxがReact Routerを正しく扱えるように設定
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# ポート80を公開
EXPOSE 80

# nginxを起動
CMD ["nginx", "-g", "daemon off;"]
