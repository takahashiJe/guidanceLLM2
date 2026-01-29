import os
import time
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

# app_db_models.pyで定義したBaseをインポート
# Note: このスクリプトは /app/backend から実行される想定
from worker.app_db_models import Base

# 環境変数からデータベース接続情報を取得
DB_USER = os.getenv("APP_DB_USER", "app_user")
DB_PASSWORD = os.getenv("APP_DB_PASSWORD", "app_password")
# docker-compose.yml内のサービス名をホストとして使用
DB_HOST = os.getenv("APP_DB_HOST", "app-db") 
DB_PORT = os.getenv("APP_DB_PORT", "5432")
DB_NAME = os.getenv("APP_DB_NAME", "app_db")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_tables():
    """データベースに接続し、テーブルを作成する"""
    
    max_retries = 10
    for i in range(max_retries):
        try:
            engine = create_engine(DATABASE_URL)
            # 接続を試みる
            with engine.connect() as connection:
                print("--- App DB connection successful. ---")
                
                print("--- Creating tables for App DB... ---")
                # Baseに紐づくテーブルをすべて作成
                Base.metadata.create_all(engine)
                print("--- Tables for App DB created successfully. ---")
                return
        except OperationalError as e:
            print(f"--- App DB connection failed: {e}. Retrying ({i+1}/{max_retries})... ---")
            time.sleep(5)
    
    print(f"--- Could not connect to App DB after {max_retries} retries. Aborting. ---")
    exit(1)

if __name__ == "__main__":
    create_tables()
