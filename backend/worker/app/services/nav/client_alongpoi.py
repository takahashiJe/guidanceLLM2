import os
import httpx

ALONGPOI_BASE = os.getenv("ALONGPOI_BASE", "http://svc-alongpoi:9102")

def post_along(payload: dict) -> dict:
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{ALONGPOI_BASE.rstrip('/')}/along", json=payload)
    r.raise_for_status()
    return r.json()
