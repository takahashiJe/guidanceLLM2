# guidanceLLM2/frontend/Dockerfile

# --- 開発ステージ ---
# Node.jsの最新LTSバージョンをベースイメージとして使用
FROM node:20-alpine AS dev

# 作業ディレクトリを設定
WORKDIR /app

# package.json と package-lock.json をコピー
COPY ./package*.json ./

# プロジェクトの依存関係をインストール
# 開発依存も全てインストールする
RUN npm install jwt-decode && npm install

# アプリケーションのソースコードはボリュームマウントされるため、ここではコピーしない
# COPY . .

# Vite開発サーバーのデフォルトポートを公開
EXPOSE 5173

# コンテナ起動時に開発サーバーを実行
# npm run dev は Vite を使って開発サーバーを起動する
CMD ["npm", "run", "dev"]