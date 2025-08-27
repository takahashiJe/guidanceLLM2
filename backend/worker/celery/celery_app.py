import os
from celery import Celery

# 環境変数から接続情報を取得                                                                                                                   
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Celeryアプリケーションのインスタンスを作成                                                                                                   
celery_app = Celery(
    "guidance",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[""] # 実行するタスクが定義されているモジュールを指定                                                              
)

# Celeryの設定（オプション）                                                                                                                   
celery_app.conf.update(
    task_track_started=True,
)