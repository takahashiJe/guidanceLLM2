from __future__ import annotations

import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:30")


def generate(prompt: str, model: str | None = None, options: dict | None = None, timeout: float = 60.0) -> str:
    """
    Ollama /api/generate を使用して 1 ショット生成（非ストリーミング）。
    """
    model = model or DEFAULT_MODEL
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False
    }
    if options:
        body["options"] = options

    url = f"{OLLAMA_URL.rstrip('/')}/api/chat"
    print(f"DEBUG: POST {url} with body: {body}")
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body)
        r.raise_for_status()
        data = r.json()
        print(f"DEBUG: Response JSON: {data}")
        txt = data.get("message", {}).get("content") or ""
        return txt.strip()
    except Exception as e:
        print((f"発生した例外: {e}"))
        # フェイルセーフ：プロンプトの頭を返す（本番ではログに出す）
        head = prompt[:200].strip()
        return f"[LLM unavailable] {head}"
