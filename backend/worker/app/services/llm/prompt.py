from __future__ import annotations

from typing import List, Dict

LANG_HINT = {
    "ja": "日本語",
    "en": "English",
    "zh": "中文",
}

STYLE_HINT = {
        "ja": "落ち着いたガイド口調で、約45〜60秒（200〜300字程度）。固有名詞は正確に、過度な比喩は避ける。",
        "en": "Warm guide tone, about 45–60s (120–160 words). Precise proper nouns, minimal florid language.",
        "zh": "温和的导览口吻，约45–60秒（120–160词）。专有名词要准确，避免过度修辞。",
}

SAFETY_FOOTER = {
    "ja": "安全配慮: 天候・足元・野生動物への配慮を一言添えてください。過度な行動の推奨は避けます。",
    "en": "Safety: briefly remind about weather, footing, and wildlife awareness. Avoid encouraging risky behavior.",
    "zh": "安全提示：请简要提醒注意天气、路况与野生动物。避免鼓励冒险行为。",
}

CONDITION_HINTS = {
    "ja": {
        "weather_1": "このスポットは曇り空です。どのスポットが曇りなのかわかるようにスポット名を含めてください。案内の最後に、天候の変化に注意するよう促す一文を自然な形で加えてください。",
        "weather_2": "このスポットは雨が降っています。どのスポットが雨なのかわかるようにスポット名を含めてください。案内の最後に、足元が滑りやすいことへの注意喚起を自然な形で加えてください。",
        "congestion_1": "このスポットは少し混雑しています。どのスポットが混雑しているのかわかるようにスポット名を含めてください。案内の最後に、周囲の人に配慮して楽しむよう促す短い一文を加えてください。",
        "congestion_2": "このスポットは大変混雑しています。どのスポットが混雑しているのかわかるようにスポット名を含めてください。案内の最後に、迷子や落とし物に注意し、譲り合って楽しむよう促す一文を加えてください。",
    },
    "en": {
        "weather_1": "This spot is cloudy. Please include the spot name so it's clear which spot is cloudy. At the end of the guide, naturally add a sentence urging people to be mindful of weather changes.",
        "weather_2": "It's raining at this location. Please include the location name so it's clear which spot is experiencing rain. At the end of the announcement, naturally add a warning about slippery footing.",
        "congestion_1": "This spot is a bit crowded. Please include the spot name so people know which one is busy. At the end of the guide, add a short sentence encouraging visitors to enjoy themselves while being considerate of others around them.",
        "congestion_2": "This spot is extremely crowded. Please include the spot name so visitors can identify which areas are busy. At the end of the notice, add a sentence reminding visitors to be mindful of lost children and lost items, and to enjoy the area by being considerate of others.",
    },
    "zh": {
        "weather_1": "该区域天气为多云。请包含区域名称以便明确区分多云区域。在导览结尾处，请自然地添加一句提醒注意天气变化的提示语。",
        "weather_2": "该区域正在下雨。请包含区域名称以便明确雨势位置。在指引结尾处，请自然地添加地面湿滑的注意事项。",
        "congestion_1": "该景点略显拥挤。请包含景点名称以便了解具体拥挤区域。在导览结尾处，请添加一句简短提示，提醒游客注意照顾周围人群，共同享受游览乐趣。",
        "congestion_2": "该景点人流密集。请注明具体景点名称以便游客知晓拥挤区域。在导览结尾处，请添加一句提示语，提醒游客注意防止走失和遗失物品，并倡导互相礼让、愉快游玩。",
    },
}

def _join_context(ctx: List[Dict], max_chars: int = 8000) -> str:
    # 単純に text を連結（必要なら将来トークン制御）
    texts = []
    total = 0
    for c in ctx or []:
        t = (c.get("text") or "").strip()
        if not t:
            continue
        total += len(t)
        texts.append(t)
        if total >= max_chars:
            break
    return "\n\n".join(texts)


def build_prompt(spot: Dict, ctx: List[Dict], lang: str,) -> str:
    """
    音声ナレーション向けのプロンプトを構築。
    spot辞書に situation が含まれるかで、生成するプロンプトを切り替える。
    - situation 無し: 通常のスポット説明（RAG利用）
    - situation 有り: 天候・混雑度に応じた状況別案内
    """
    lang_label = LANG_HINT.get(lang, lang)
    name = spot.get("name") or spot.get("spot_id", "this spot")
    situation = spot.get("situation")

    # --- situation がある場合：状況説明のプロンプトを生成 ---
    if situation:
        condition_instruction = CONDITION_HINTS.get(lang, {}).get(situation, "")

        prompt = f"""
[TASK=Generate a situational guidance message] [LANGUAGE={lang}|{lang_label}]
あなたは鳥海山エリアを訪れる観光客向けのプロのツアーガイドです。

特定のスポットにおける状況に応じた、簡潔な音声案内を作成してください。

スポット名: {name} (ID: {spot.get('spot_id')})
現在の状況: {condition_instruction}

指示:
- 必ずスポット名から始め、「{name}は現在、少し混雑しています。」のように、現在の状況を伝える文章を作成してください。
- 非常に簡潔（1〜2文程度）な、{lang_label}の話し言葉で記述してください。
- 役立つ、分かりやすい口調を心がけてください。
- スポットの歴史や自然に関する追加情報は含めず、与えられた状況に関する案内に徹してください。
- 出力はプレーンテキストのみとします。
""".strip()
        return prompt

    # --- situation がない場合：スポットのガイダンステキストのプロンプトを生成 ---
    else:
        style_note = STYLE_HINT.get(lang, "narration")
        desc = (spot.get("description") or "").strip()

        context_block = _join_context(ctx, max_chars=8000)

        facts_lines = []
        if desc:
            facts_lines.append(f"- POI.description: {desc}")
        if context_block:
            facts_lines.append(f"- RAG:\n{context_block}")
        facts_txt = "\n".join(facts_lines) if facts_lines else "- (no extra context)"

        prompt = f"""
[LANGUAGE={lang}|{lang_label}] [STYLE=guidance]
あなたは鳥海山エリアを訪れる観光客向けのプロのツアーガイドです。

スポット名: {name} (ID: {spot.get('spot_id')})
参考情報:
{facts_txt}

上記の参考情報に基づき、{lang_label}で話すためのナレーション原稿を作成してください。
制約:
- {style_note}
- 構成: 1)短い導入、2)主要な事実・歴史・自然、3)豆知識、4)安全への言及。
- 不確かな情報は避け、不明な点は簡潔にそう述べる。
- 「この資料では」や「文脈によると」といった表現は使わないでください。
- 出力はプレーンテキストのみとします。

{SAFETY_FOOTER.get(lang, '')}
""".strip()
        return prompt

