from __future__ import annotations

import os
from typing import List, Dict

from backend.worker.app.services.llm import retriever, prompt as prompt_mod, ollama


def retrieve_context(spot_id: str, lang: str):
    # そのまま委譲（unit／integration テストの monkeypatch しやすさも維持）
    return retriever.retrieve_context(spot_id, lang)


def generate_text(prompt: str) -> str:
    # Ollama に投げる（モデルは環境変数で選択）
    model = os.getenv("OLLAMA_MODEL", "Qwen3:30")
    return ollama.generate(prompt, model=model)


def generate_for_spot(spot: Dict, lang: str, style: str = "narration") -> str:
    """
    スポット個別の生成。コンテキストが空でも description を必ず反映する。
    - retriever で文脈取得
    - prompt.build_prompt で description を必ず含める
    - ollama.generate で出力
    """
    ctx = retrieve_context(spot.get("spot_id"), lang)
    # build_prompt は常に description を Facts に含める実装
    ptxt = prompt_mod.build_prompt(spot, ctx, lang, style=style)
    return generate_text(ptxt)
