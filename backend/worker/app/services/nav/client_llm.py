
from __future__ import annotations

import logging
from backend.api.celery_app import celery_app

logger = logging.getLogger(__name__)

def post_describe(payload: dict) -> dict:
    """
    LLMサービスのCeleryタスクを呼び出す。
    """
    try:
        # `llm.describe` タスクを `llm` キューに送信し、同期的に結果を待つ
        async_result = celery_app.send_task("llm.describe", args=[payload], queue="llm")
        # タスクが完了するまで待機し、結果を取得する
        result = async_result.get(timeout=300)  # タイムアウトを秒単位で設定
        return result
    except Exception as e:
        logger.exception("LLM service task failed")
        raise RuntimeError("LLM service task failed") from e
