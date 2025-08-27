import os
import httpx

ROUTING_BASE = os.getenv("ROUTING_BASE", "http://svc-routing:9101")

def post_route(payload: dict) -> dict:
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{ROUTING_BASE}/route", json=payload)
    r.raise_for_status()
    return r.json()
