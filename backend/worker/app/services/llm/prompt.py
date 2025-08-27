from __future__ import annotations

from typing import List, Dict

LANG_HINT = {
    "ja": "日本語",
    "en": "English",
    "zh": "中文",
}

STYLE_HINT = {
    "narration": {
        "ja": "落ち着いたガイド口調で、約45〜60秒（200〜300字程度）。固有名詞は正確に、過度な比喩は避ける。",
        "en": "Warm guide tone, about 45–60s (120–160 words). Precise proper nouns, minimal florid language.",
        "zh": "温和的导览口吻，约45–60秒（120–160词）。专有名词要准确，避免过度修辞。",
    }
}

SAFETY_FOOTER = {
    "ja": "安全配慮: 天候・足元・野生動物への配慮を一言添えてください。過度な行動の推奨は避けます。",
    "en": "Safety: briefly remind about weather, footing, and wildlife awareness. Avoid encouraging risky behavior.",
    "zh": "安全提示：请简要提醒注意天气、路况与野生动物。避免鼓励冒险行为。",
}


def _join_context(ctx: List[Dict], max_tokens: int = 800) -> str:
    # 単純に text を連結（必要なら将来トークン制御）
    texts = []
    length = 0
    for c in ctx or []:
        t = (c.get("text") or "").strip()
        if not t:
            continue
        length += len(t)
        texts.append(t)
        if length >= max_tokens * 4:  # 適当な上限
            break
    return "\n\n".join(texts)


def build_prompt(spot: Dict, ctx: List[Dict], lang: str, style: str = "narration") -> str:
    """
    音声ナレーション向けのプロンプトを構築。
    - 言語・スタイルの明示
    - スポット名/説明（もしあれば）と RAG 文脈
    - 構成指示（導入→要点→豆知識→安全ひとこと）
    """
    lang_label = LANG_HINT.get(lang, lang)
    style_note = STYLE_HINT.get(style, {}).get(lang, style)
    name = spot.get("name") or spot.get("spot_id", "this spot")
    desc = (spot.get("description") or "").strip()

    context_block = _join_context(ctx, max_tokens=800)
    # description は常に含める（コンテキスト0件のフェイルセーフにもなる）
    base_facts = []
    if desc:
        base_facts.append(f"- POI.description: {desc}")
    if context_block:
        base_facts.append(f"- RAG:\n{context_block}")
    base_facts_txt = "\n".join(base_facts) if base_facts else "- (no extra context)"

    prompt = f"""
[LANGUAGE={lang}|{lang_label}] [STYLE={style}|ナレーション]
You are a professional tour guide for visitors around Mt. Chokai area.

Spot: {name} (ID: {spot.get('spot_id')})
Facts:
{base_facts_txt}

Write a spoken narration in {lang_label}.
Constraints:
- {style_note}
- Structure: 1) short intro; 2) key facts/history/nature; 3) fun tidbit; 4) safety reminder.
- Avoid speculation; if unknown, say so briefly.
- Keep it self-contained; don't reference 'the document' or 'the context'.
- Output plain text ONLY.

{SAFETY_FOOTER.get(lang, '')}
""".strip()

    return prompt
