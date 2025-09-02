# services/nav/celery_app.py
import os
from celery import Celery

celery_app = Celery(
    "nav",
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
    task_default_queue="nav",
)

celery_app.autodiscover_tasks(["backend.worker.app.services.nav"], force=True)

celery_app.conf.task_routes = {
    "nav.*": {"queue": "nav"},
}