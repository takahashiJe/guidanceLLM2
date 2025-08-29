import os
import httpx

VOICE_BASE = os.getenv("VOICE_BASE", "http://svc-voice:9104")

def post_synthesize(payload: dict) -> dict:
    with httpx.Client(timeout=60) as client:
        r = client.post(f"{VOICE_BASE.rstrip('/')}/synthesize", json=payload)
    r.raise_for_status()
    return r.json()
