from __future__ import annotations

import os
from typing import Dict, List

from backend.worker.app.services.llm import retriever, prompt as prompt_mod, ollama


def retrieve_context(spot_ref: Dict, lang: str):
    # md_slug / spot_id / name を考慮した文脈取得
    return retriever.retrieve_context(spot_ref, lang)


def generate_text(prompt: str) -> str:
    # Ollama で生成
    model = os.getenv("OLLAMA_MODEL", "Qwen3:30")
    return ollama.generate(prompt, model=model)


def generate_for_spot(spot: Dict, lang: str, style: str = "narration") -> str:
    """
    スポット個別の生成。
    - md_slug があれば該当 MD を探索
    - 見つからなくても description を必ず Facts に含める（プロンプト側の仕様）
    """
    ctx = retrieve_context(spot, lang)
    ptxt = prompt_mod.build_prompt(spot, ctx, lang, style=style)
    return generate_text(ptxt)
