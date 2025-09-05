# backend/worker/app/services/nav/client_llm.py

from __future__ import annotations

import os
import httpx
import logging

logger = logging.getLogger(__name__)

# LLMサービスのベースURLを設定 (環境変数 or デフォルト値)
LLM_BASE = os.getenv("LLM_BASE", "http://svc-llm:9103")
REQ_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")) # LLMは時間がかかる可能性があるので少し長めに

def post_describe(payload: dict) -> dict:
    """
    FastAPIで実装されたLLMサービスにHTTP POSTリクエストを送信する。
    """
    url = f"{LLM_BASE}/describe"
    try:
        with httpx.Client() as client:
            res = client.post(url, json=payload, timeout=REQ_TIMEOUT)
            res.raise_for_status()  # ステータスコードが 2xx でない場合に例外を発生
            return res.json()
    except httpx.RequestError as e:
        logger.exception(f"LLM service request failed: {e.request.method} {e.request.url}")
        raise RuntimeError(f"Could not connect to LLM service at {url}") from e
    except httpx.HTTPStatusError as e:
        logger.error(f"LLM service returned an error: {e.response.status_code} - {e.response.text}")
        # エラーの詳細をラップして再送出
        raise RuntimeError(f"LLM service error: {e.response.status_code}, detail: {e.response.text}") from e