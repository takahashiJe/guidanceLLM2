from __future__ import annotations

from fastapi import FastAPI, HTTPException
from backend.worker.celery_app import celery_app
from backend.worker.app.services.llm.tasks import DescribeRequest, DescribeResponse
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="llm service")

@app.post("/describe", response_model=DescribeResponse)
def describe_endpoint(req: DescribeRequest):
    """
    Accepts a description request, forwards it to a Celery worker,
    and waits for the result.
    """
    try:
        # Celeryタスクを呼び出し、結果を同期的に待つ
        async_result = celery_app.send_task(
            "llm.describe",
            args=[req.model_dump()],
            queue="generation"
        )
        # タイムアウトを長めに設定
        result = async_result.get(timeout=3000)
        return result
    except Exception as e:
        logger.exception("Failed to get result from Celery task")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
