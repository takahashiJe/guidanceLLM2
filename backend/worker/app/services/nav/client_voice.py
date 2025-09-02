import os
import httpx

VOICE_BASE = os.getenv("VOICE_BASE", "http://svc-voice:9104")

def post_synthesize(payload: dict) -> dict:
    """（お試し用）音声を合成するが、ファイルには保存しない"""
    with httpx.Client(timeout=60) as client:
        r = client.post(f"{VOICE_BASE.rstrip('/')}/synthesize", json=payload)
    r.raise_for_status()
    return r.json()

def post_synthesize_and_save(payload: dict) -> dict:
    """
    【本番用】複数のテキストを音声化し、指定された pack_id ディレクトリに保存する。
    成功すると、各音声ファイルへのURLを含むJSONを返す。
    """
    with httpx.Client(timeout=300) as client: # タイムアウトを長めに設定
        r = client.post(f"{VOICE_BASE.rstrip('/')}/synthesize_and_save", json=payload)
    r.raise_for_status()
    return r.json()