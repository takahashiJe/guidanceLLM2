from __future__ import annotations
from celery import Celery
import os

redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = os.getenv("REDIS_PORT", "6379")
broker_url = f"redis://{redis_host}:{redis_port}/0"
result_backend = f"redis://{redis_host}:{redis_port}/1"

celery_app = Celery(
    "llm_worker",
    broker=broker_url,
    backend=result_backend,
    include=["backend.worker.app.services.llm.tasks"],
)
