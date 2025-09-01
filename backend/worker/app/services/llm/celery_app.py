# services/llm/celery_app.py
import os
from celery import Celery

celery_app = Celery(
    "llm",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=os.getenv("TZ", "Asia/Tokyo"),
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
)

celery_app.autodiscover_tasks(["backend.worker.app.services.llm"], force=True)

celery_app.conf.task_routes = {
    "llm.describe": {"queue": "llm"},
}