import os
import time
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from worker.app_db_models import Base, SpotRealtime


DB_USER = os.getenv("APP_DB_USER", "app_user")
DB_PASSWORD = os.getenv("APP_DB_PASSWORD", "app_password")
DB_HOST = os.getenv("APP_DB_HOST", "app-db")
DB_PORT = os.getenv("APP_DB_PORT", "5432")
DB_NAME = os.getenv("APP_DB_NAME", "app_db")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def create_spot_realtime_table():
    """spot_realtime テーブルを作成する。既存の場合は何もしない。"""
    max_retries = 10
    for attempt in range(max_retries):
        try:
            engine = create_engine(DATABASE_URL)
            with engine.begin() as connection:
                # SpotRealtime を metadata に確実に登録した上で create
                Base.metadata.create_all(
                    bind=connection,
                    tables=[SpotRealtime.__table__],
                )
                print("--- spot_realtime table ready. ---")
                return
        except OperationalError as exc:
            print(
                f"--- App DB connection failed: {exc}. "
                f"Retrying ({attempt + 1}/{max_retries})... ---"
            )
            time.sleep(5)
    raise RuntimeError(
        f"Could not connect to App DB after {max_retries} retries."
    )


if __name__ == "__main__":
    create_spot_realtime_table()
