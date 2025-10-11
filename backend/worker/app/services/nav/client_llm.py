from __future__ import annotations

import os
import httpx
import logging

logger = logging.getLogger(__name__)

LLM_SVC_BASE = os.getenv("LLM_SVC_BASE", "http://svc-llm:9103")
REQ_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "3000"))

def post_describe(payload: dict) -> dict:
    """
    Makes an HTTP POST request to the llm service's /describe endpoint.
    """
    url = f"{LLM_SVC_BASE}/describe"
    try:
        # with httpx.Client(timeout=REQ_TIMEOUT) as client:
        with httpx.Client(timeout=REQ_TIMEOUT) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            return response.json()
    except httpx.RequestError as e:
        logger.exception(f"Request to LLM service failed: {e}")
        raise RuntimeError(f"LLM service is unavailable: {e}") from e
    except httpx.HTTPStatusError as e:
        logger.exception(f"Error response from LLM service: {e.response.status_code} {e.response.text}")
        raise RuntimeError(f"Error from LLM service: {e.response.text}") from e