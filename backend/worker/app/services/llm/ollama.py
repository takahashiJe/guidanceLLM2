from __future__ import annotations

import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_GENERATION_MODEL", "qwen3:14b")


def generate(prompt: str, model: str | None = None, options: dict | None = None, timeout: float = 3000.0) -> str:
    """
    Ollama /api/chat を使用して 1 ショット生成（非ストリーミング）。
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
        # 同期クライアントの正しい呼び出し方に修正
        r = httpx.post(url, json=body, timeout=timeout)
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
