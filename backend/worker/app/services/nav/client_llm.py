import os
import httpx

LLM_BASE = os.getenv("LLM_BASE", "http://svc-llm:9103")

def post_describe(payload: dict) -> dict:
    with httpx.Client(timeout=60) as client:
        r = client.post(f"{LLM_BASE.rstrip('/')}/describe", json=payload)
    r.raise_for_status()
    return r.json()
