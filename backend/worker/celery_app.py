from __future__ import annotations
from celery import Celery
from kombu import Queue
import os

# このファイルがプロジェクト唯一のCelery設定ファイルとなる

redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = os.getenv("REDIS_PORT", "6379")
broker_url = f"redis://{redis_host}:{redis_port}/0"
result_backend = f"redis://{redis_host}:{redis_port}/1"

# Celeryアプリケーションをインスタンス化
celery_app = Celery(
    "guidance-llm-celery",
    broker=broker_url,
    backend=result_backend,
    # プロジェクト内の全てのタスクモジュールをここで指定する
    include=[
        # 既存のLLMサービスが使用するタスク
        "backend.worker.app.services.llm.tasks", 
        # 新しいAIエージェントが使用するタスク
        "backend.worker.agent_app.llm_tasks"
    ],
)

# Celeryの設定
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=os.getenv("TZ", "Asia/Tokyo"),
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="generation",
    task_queues=(
        Queue("generation", routing_key="generation"),
        Queue("embedding", routing_key="embedding"),
    ),
    task_routes={
        "llm.describe": {"queue": "generation", "routing_key": "generation"},
        "llm_tasks.generate_text": {"queue": "generation", "routing_key": "generation"},
        "llm_tasks.generate_embedding": {"queue": "embedding", "routing_key": "embedding"},
    },
)
