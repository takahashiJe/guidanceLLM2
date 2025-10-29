import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

# AgentStateの循環参照を避けるため、型チェック時のみインポート
if TYPE_CHECKING:
    from .agent import AgentState


SUPPORTED_PROMPT_LANGS = {"ja", "en", "zh"}


def _select_language(lang: Optional[str]) -> str:
    normalized = _normalize_lang(lang or "ja")
    if normalized not in SUPPORTED_PROMPT_LANGS:
        return "ja"
    return normalized


INTENT_PARSER_PROMPTS = {
    "ja": """あなたは観光チャットボットの意図解析器です。以下のJSONスキーマに厳密に従い、<json>{...}</json>のみを出力してください。

JSONスキーマ:
{
  "type": "object",
  "required": ["intent", "entities"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": [
        "request_recommendation",
        "add_to_plan",
        "delete_from_plan",
        "reorder_plan",
        "restart_plan",
        "ask_question",
        "affirmation",
        "negation",
        "chitchat"
      ]
    },
    "entities": {
      "type": "object",
      "properties": {
        "spot_ids":    { "type": "array", "items": { "type": "string" } },
        "spot_names":  { "type": "array", "items": { "type": "string" } },
        "keywords":    { "type": "array", "items": { "type": "string" } },
        "reorder_info": {
          "type": "object",
          "properties": {
            "target_spot":      { "type": "string" },
            "destination_spot": { "type": "string" },
            "position":         { "type": "string", "enum": ["before", "after", "first", "last"] }
          },
          "required": ["target_spot", "position"],
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

ルール:
- 余計な文字列は禁止。<json>タグの内側だけを返す。
- スキーマに載っていないキーを追加しない。
- 値が不明なプロパティはキーごと省略し、null や空文字は使わない。
- JSONを生成できない場合のみ <json>{"intent":"chitchat","entities":{}}</json> を返す。

ユーザーの最新の発話と会話履歴を基に、解析結果を<json>...</json>のブロックのみで出力してください。
""",
    "en": """You are the intent parser for a sightseeing chatbot. Follow the JSON schema below strictly and output only <json>{...}</json>.

JSON schema:
{
  "type": "object",
  "required": ["intent", "entities"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": [
        "request_recommendation",
        "add_to_plan",
        "delete_from_plan",
        "reorder_plan",
        "restart_plan",
        "ask_question",
        "affirmation",
        "negation",
        "chitchat"
      ]
    },
    "entities": {
      "type": "object",
      "properties": {
        "spot_ids":    { "type": "array", "items": { "type": "string" } },
        "spot_names":  { "type": "array", "items": { "type": "string" } },
        "keywords":    { "type": "array", "items": { "type": "string" } },
        "reorder_info": {
          "type": "object",
          "properties": {
            "target_spot":      { "type": "string" },
            "destination_spot": { "type": "string" },
            "position":         { "type": "string", "enum": ["before", "after", "first", "last"] }
          },
          "required": ["target_spot", "position"],
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

Rules:
- Do not output any extra text. Return only the content inside <json>...</json>.
- Do not add keys that are not defined in the schema.
- Omit keys whose values are unknown; never use null or empty strings.
- Only when JSON cannot be produced, return <json>{"intent":"chitchat","entities":{}}</json>.

Use the latest user utterance and the chat history to produce the analysis and output only the <json>...</json> block.
""",
    "zh": """你是一个旅游聊天机器人的意图解析器。必须严格遵守以下 JSON 架构，并且只输出 <json>{...}</json>。

JSON 架构：
{
  "type": "object",
  "required": ["intent", "entities"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": [
        "request_recommendation",
        "add_to_plan",
        "delete_from_plan",
        "reorder_plan",
        "restart_plan",
        "ask_question",
        "affirmation",
        "negation",
        "chitchat"
      ]
    },
    "entities": {
      "type": "object",
      "properties": {
        "spot_ids":    { "type": "array", "items": { "type": "string" } },
        "spot_names":  { "type": "array", "items": { "type": "string" } },
        "keywords":    { "type": "array", "items": { "type": "string" } },
        "reorder_info": {
          "type": "object",
          "properties": {
            "target_spot":      { "type": "string" },
            "destination_spot": { "type": "string" },
            "position":         { "type": "string", "enum": ["before", "after", "first", "last"] }
          },
          "required": ["target_spot", "position"],
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

规则：
- 禁止输出额外文本，只能返回 <json>...</json> 内的内容。
- 不要添加架构中未定义的键。
- 无法确定的属性请整键省略，绝对不要使用 null 或空字符串。
- 只有在无法生成 JSON 时才能返回 <json>{"intent":"chitchat","entities":{}}</json>。

请根据最新的用户发言和会话历史，生成解析结果，并仅返回 <json>...</json> 块。
""",
}


INTENT_PARSER_RETRY_PROMPTS = {
    "ja": """!!! 前回の出力は無効です !!!
以下のJSONスキーマに従い、<json>{...}</json>のみを返してください。余計なテキストは禁止です。

JSONスキーマ:
{
  "type": "object",
  "required": ["intent", "entities"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": [
        "request_recommendation",
        "add_to_plan",
        "delete_from_plan",
        "reorder_plan",
        "restart_plan",
        "ask_question",
        "affirmation",
        "negation",
        "chitchat"
      ]
    },
    "entities": {
      "type": "object",
      "properties": {
        "spot_ids":    { "type": "array", "items": { "type": "string" } },
        "spot_names":  { "type": "array", "items": { "type": "string" } },
        "keywords":    { "type": "array", "items": { "type": "string" } },
        "reorder_info": {
          "type": "object",
          "properties": {
            "target_spot":      { "type": "string" },
            "destination_spot": { "type": "string" },
            "position":         { "type": "string", "enum": ["before", "after", "first", "last"] }
          },
          "required": ["target_spot", "position"],
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

- スキーマにないキーは禁止。
- 値が分からないキーは省略し、nullや空文字は禁止。
 - JSONを生成できない場合のみ <json>{"intent":"chitchat","entities":{}}</json> を返す。

前回の無効な出力:
{previous_output}
""",
    "en": """!!! The previous output was invalid !!!
Follow the JSON schema below and return only <json>{...}</json>. Extra text is forbidden.

JSON schema:
{
  "type": "object",
  "required": ["intent", "entities"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": [
        "request_recommendation",
        "add_to_plan",
        "delete_from_plan",
        "reorder_plan",
        "restart_plan",
        "ask_question",
        "affirmation",
        "negation",
        "chitchat"
      ]
    },
    "entities": {
      "type": "object",
      "properties": {
        "spot_ids":    { "type": "array", "items": { "type": "string" } },
        "spot_names":  { "type": "array", "items": { "type": "string" } },
        "keywords":    { "type": "array", "items": { "type": "string" } },
        "reorder_info": {
          "type": "object",
          "properties": {
            "target_spot":      { "type": "string" },
            "destination_spot": { "type": "string" },
            "position":         { "type": "string", "enum": ["before", "after", "first", "last"] }
          },
          "required": ["target_spot", "position"],
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

- Keys outside the schema are prohibited.
- Omit keys whose values are unknown; do not use null or empty strings.
- Only when JSON cannot be generated may you return <json>{"intent":"chitchat","entities":{}}</json>.

Previous invalid output:
{previous_output}
""",
    "zh": """!!! 上一次的输出无效 !!!
请遵循以下 JSON 架构，只能返回 <json>{...}</json>。禁止额外文本。

JSON 架构：
{
  "type": "object",
  "required": ["intent", "entities"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": [
        "request_recommendation",
        "add_to_plan",
        "delete_from_plan",
        "reorder_plan",
        "restart_plan",
        "ask_question",
        "affirmation",
        "negation",
        "chitchat"
      ]
    },
    "entities": {
      "type": "object",
      "properties": {
        "spot_ids":    { "type": "array", "items": { "type": "string" } },
        "spot_names":  { "type": "array", "items": { "type": "string" } },
        "keywords":    { "type": "array", "items": { "type": "string" } },
        "reorder_info": {
          "type": "object",
          "properties": {
            "target_spot":      { "type": "string" },
            "destination_spot": { "type": "string" },
            "position":         { "type": "string", "enum": ["before", "after", "first", "last"] }
          },
          "required": ["target_spot", "position"],
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}

- 禁止使用架构之外的键。
- 无法确定的键请整键省略，不能使用 null 或空字符串。
- 只有在无法生成 JSON 时才可以返回 <json>{"intent":"chitchat","entities":{}}</json>。

上一次的无效输出：
{previous_output}
""",
}


PROFILE_EXTRACTOR_PROMPTS = {
    "ja": """あなたはユーザー発話から旅行プロフィールを抽出するアシスタントです。以下のJSON形式のみを出力してください。

{
  "age": "…",                // 例: "20代", "30s", "50歳くらい"
  "travel_style": "…",       // 例: "ひとり旅", "家族旅行", "アクティブ派"
  "travel_frequency": "…",   // 例: "年に1-2回", "毎月", "初めて"
  "interests": ["…"],         // 例: ["自然", "温泉", "グルメ"]
  "positive_keywords": ["…"], // 任意。楽しみにしている要素
  "negative_keywords": ["…"]  // 任意。避けたい要素
}

ルール:
- JSON以外のテキストを一切書かない。
- 分からない項目はキーごと省略する（nullや空文字は禁止）。
- 配列は文字列のリストとして出力する。
""",
    "en": """You are an assistant that extracts a travel profile from the user's utterance. Output only JSON in the following structure.

{
  "age": "…",                // e.g., "20s", "30s", "around 50"
  "travel_style": "…",       // e.g., "solo travel", "family trip", "active"
  "travel_frequency": "…",   // e.g., "1-2 times a year", "monthly", "first time"
  "interests": ["…"],         // e.g., ["nature", "hot springs", "gourmet"]
  "positive_keywords": ["…"], // optional: things they look forward to
  "negative_keywords": ["…"]  // optional: things to avoid
}

Rules:
- Do not output anything other than the JSON object.
- Omit keys whose values cannot be inferred (do not use null or empty strings).
- Arrays must be output as lists of strings.
""",
    "zh": """你是一名助手，需要从用户的发言中提取旅行画像。只能输出以下结构的 JSON。

{
  "age": "…",                // 例："20多岁"、"30岁出头"、"大约50岁"
  "travel_style": "…",       // 例："独自旅行"、"家庭出游"、"喜欢户外活动"
  "travel_frequency": "…",   // 例："一年1-2次"、"每月"、"第一次"
  "interests": ["…"],         // 例：["自然","温泉","美食"]
  "positive_keywords": ["…"], // 可选。期待的要素
  "negative_keywords": ["…"]  // 可选。不想要的要素
}

规则：
- 除了 JSON 以外不要输出任何文本。
- 无法确定的项目请整键省略，禁止使用 null 或空字符串。
- 数组必须以字符串列表的形式输出。
""",
}


PROFILE_QUESTION_PROMPTS = {
    "ja": """あなたは観光ガイドです。ユーザーから旅行プロフィールを伺う短い質問メッセージを作成してください。入力として与えられる`missing_fields`の各項目について、次の条件を満たしてください。

ルール:
- 2〜3個の項目それぞれに、「例」を含めた案内文を付ける（箇条書き可）。
- ユーザーが答えられる範囲で構わない旨を各項目または冒頭に明記する。
- 出力は自然文のみで構成し、丁寧で親しみやすいトーンにする。
- 文末で自由入力を促す一文を加える。
""",
    "en": """You are a tour guide. Write a short message asking the user for their travel profile. For each field listed in `missing_fields`, satisfy the following conditions.

Rules:
- Provide guidance for 2-3 items, each including an example (bullet points allowed).
- Make it clear at the beginning or within each item that partial answers are welcome.
- The output must be natural prose with a polite, friendly tone.
- End with a sentence inviting the user to share anything freely.
""",
    "zh": """你是一名导游。请写一段简短的消息，向用户询问旅行画像信息。针对 `missing_fields` 中的每个字段，请满足以下要求。

规则：
- 提供 2～3 个项目的提示，并包含示例（可以使用项目符号）。
- 在开头或各条目中说明，用户只需回答自己方便的部分即可。
- 输出需为礼貌、亲切的自然语句。
- 最后加上一句鼓励用户自由补充的句子。
""",
}


RESPONSE_PROMPT_STRINGS = {
    "ja": {
        "base_prompt": """あなたは鳥海エリア専門の親切なツアーガイドです。ユーザーの言語「{lang}」で応答してください。

# 出力形式に関する注意
- 常にMarkdown形式で出力し、適切な見出しや箇条書きを活用してください。
- 文章だけではなく、見出し（#, ## など）・リスト（- や 1.）・区切り線を必要に応じて使ってください。

# 現在の状況
{itinerary_summary}
    """,
        "itinerary_intro": "現在の周遊計画は以下の通りです。",
        "itinerary_empty": "現在、周遊計画にスポットは登録されていません。",
        "itinerary_bullet": "- {spot_name}",
        "recommendation_section_title": "# 提案する観光スポット",
        "recommendation_template": """## 推薦スポット{index}: {spot_name}
- 推薦理由のヒント: {reason_text}
- スポット概要: {summary}
{realtime_text}- 詳細説明:
---
{context}
---

""",
        "summary_fallback": "（説明はMarkdownを参照）",
        "realtime_heading": "・リアルタイム情報:",
        "realtime_weather": "  - 天気: {label}",
        "realtime_congestion": "  - 混雑状況: {label}",
        "realtime_updated": "  - 最終更新: {timestamp}",
        "realtime_missing": "・リアルタイム情報: 取得できませんでした。",
        "instruction_heading": "# 指示",
        "recommendation_instruction": "上記で提案した観光スポットの魅力が伝わるように、詳細説明を基に具体的に紹介してください。各スポットについて、リアルタイム情報（天気・混雑状況）の両方が提供されている場合は、それぞれを短い文章で必ず紹介し、その状況がどのように体験に影響するかを一言添えてください。どちらか一方のみ取得できた場合は、その情報だけでも明記し、もう一方が不明であることを補足してください。情報が全く取得できなかった場合は、その旨を丁寧に伝えてください。紹介の最後には、「どのスポットに興味がありますか？」や「計画に追加しますか？」など、ユーザーの次の行動を促す質問を必ず含めてください。既に計画に含まれているスポットを再度薦めないでください。内部ID（spot_***など）を表示しないでください。",
        "chitchat_instruction": "ユーザーの最新の発言に対して、親切なツアーガイドとして自然に会話を続けてください。周遊計画に登録済みのスポットがある場合は、その内容を正確に参照してください。内部ID（spot_***など）を表示しないでください。",
        "no_detail_fallback": "このスポットに関する詳細情報はありません。",
    },
    "en": {
        "base_prompt": """You are a friendly tour guide specializing in the Mt. Chokai area. Answer in the user's language \"{lang}\".

# Output Formatting Notes
- Always respond in Markdown, using headings (e.g., #, ##) and lists (- or 1.) where appropriate.
- Structure the content so it can be rendered directly as Markdown without additional cleanup.

# Current Situation
{itinerary_summary}
    """,
        "itinerary_intro": "The current itinerary is as follows:",
        "itinerary_empty": "There are currently no spots in the itinerary.",
        "itinerary_bullet": "- {spot_name}",
        "recommendation_section_title": "# Suggested Spots",
        "recommendation_template": """## Recommended Spot {index}: {spot_name}
- Hint for the recommendation: {reason_text}
- Spot summary: {summary}
{realtime_text}- Detailed description:
---
{context}
---

""",
        "summary_fallback": "(Refer to the Markdown description.)",
        "realtime_heading": "- Realtime information:",
        "realtime_weather": "  - Weather: {label}",
        "realtime_congestion": "  - Crowd level: {label}",
        "realtime_updated": "  - Last updated: {timestamp}",
        "realtime_missing": "- Realtime information: Unable to retrieve.",
        "instruction_heading": "# Instructions",
        "recommendation_instruction": "Using the detailed description above, vividly introduce each recommended spot. For every spot, if both realtime weather and congestion are provided, call them out explicitly in natural language and add a brief note on how each condition might affect the visit. If only one of them is available, mention the available metric and state that the other is unknown. When neither is available, say so politely. Always finish with a follow-up question such as “Would you like to add any of these to your plan?” or “Which spot sounds most interesting?”. Do not recommend spots that are already in the itinerary. Do not mention internal spot IDs (e.g., spot_***).",
        "chitchat_instruction": "Respond naturally as a friendly tour guide to the user's latest message. If the itinerary already contains spots, reference them accurately. Do not mention internal spot IDs (e.g., spot_***).",
        "no_detail_fallback": "Detailed information is not available for this spot.",
    },
    "zh": {
        "base_prompt": """你是一位专门介绍鸟海地区的贴心导游。请使用用户的语言「{lang}」进行回答。

# 输出格式说明
- 回答必须采用 Markdown 形式，合理使用标题（如 #、##）与列表（如 -、1.）。
- 内容需可直接以 Markdown 渲染，无需额外整理。

# 当前状况
{itinerary_summary}
    """,
        "itinerary_intro": "目前的行程如下：",
        "itinerary_empty": "目前行程中还没有加入任何景点。",
        "itinerary_bullet": "- {spot_name}",
        "recommendation_section_title": "# 推荐景点",
        "recommendation_template": """## 推荐景点{index}: {spot_name}
- 推荐提示: {reason_text}
- 景点概览: {summary}
{realtime_text}- 详细说明:
---
{context}
---

""",
        "summary_fallback": "（请参考 Markdown 说明。）",
        "realtime_heading": "- 实时信息:",
        "realtime_weather": "  - 天气: {label}",
        "realtime_congestion": "  - 人流情况: {label}",
        "realtime_updated": "  - 最后更新: {timestamp}",
        "realtime_missing": "- 实时信息: 暂时无法获取。",
        "instruction_heading": "# 指南",
        "recommendation_instruction": "请根据上述详细说明，热情地介绍这些推荐景点，让用户身临其境地感受体验。对于每个景点，如果同时提供了天气和人流的实时信息，请分别用自然语言说明，并简要描述这些状况会带来怎样的体验差异。若只取得其中一项，则明确告知可用的信息并说明另一项尚未取得。若完全没有实时数据，请礼貌地说明暂无相关信息。结尾务必提出后续问题，例如“要把哪一个加入行程吗？”或“哪一个更吸引您？”。不要再次推荐已在行程中的景点，也不要提到内部的景点编号（例如 spot_***）。",
        "chitchat_instruction": "请以贴心导游的身份，自然地回应用户的最新发言。若行程中已经有景点，请准确引用。不要提到内部的景点编号（例如 spot_***）。",
        "no_detail_fallback": "暂无该景点的详细信息。",
    },
}

def get_intent_parser_prompt(lang: Optional[str] = None) -> str:
    """
    ユーザーの意図を解釈するためのLLMプロンプトを返す。
    """
    return INTENT_PARSER_PROMPTS[_select_language(lang)]


def get_intent_parser_retry_prompt(previous_output: str, lang: Optional[str] = None) -> str:
    template = INTENT_PARSER_RETRY_PROMPTS[_select_language(lang)]
    return template.replace("{previous_output}", previous_output)


def get_profile_extractor_prompt(lang: Optional[str] = None) -> str:
    return PROFILE_EXTRACTOR_PROMPTS[_select_language(lang)]


def get_profile_question_prompt(lang: Optional[str] = None) -> str:
    return PROFILE_QUESTION_PROMPTS[_select_language(lang)]


def get_response_generator_prompt(state: "AgentState") -> str:
    """
    現在のエージェントの状態に基づいて、応答生成用のシステムプロンプトを構築する。
    """
    lang = state.get('language', 'ja')
    selected_lang = _select_language(lang)
    strings = RESPONSE_PROMPT_STRINGS[selected_lang]
    itinerary = state.get('itinerary', [])
    recommendations = state.get('recommendations', [])
    info_map = _load_spot_info_map()
    itinerary_set = {spot_id for spot_id in itinerary}

    # 現在の周遊計画をテキスト化
    if itinerary:
        formatted_itinerary = []
        for spot_id in itinerary:
            spot_name = _get_spot_display_name(info_map, spot_id, lang)
            formatted_itinerary.append(strings["itinerary_bullet"].format(spot_name=spot_name))
        itinerary_summary = strings["itinerary_intro"] + "\n" + "\n".join(formatted_itinerary)
    else:
        itinerary_summary = strings["itinerary_empty"]

    # プロンプトの基本部分
    base_prompt = strings["base_prompt"].format(lang=lang, itinerary_summary=itinerary_summary)

    # 推薦がある場合、推薦情報をプロンプトに追加
    filtered_recommendations = [
        rec for rec in recommendations
        if rec.get("spot_id") and rec.get("spot_id") not in itinerary_set
    ]

    if filtered_recommendations:
        reco_texts = []
        info_map = _load_spot_info_map()
        knowledge_base = Path("backend/worker/data/knowledge")
        normalized_lang = _normalize_lang(lang)

        for i, rec in enumerate(filtered_recommendations, 1):
            spot_id = rec.get("spot_id")
            reasons = rec.get("reason", [])
            realtime = rec.get("realtime") or {}

            spot_info = info_map.get(spot_id, {})
            spot_name = _get_spot_display_name(info_map, spot_id, lang)
            short_desc = _get_localized_text(spot_info.get("summary", {}), lang)

            weather_label = realtime.get("weather_label") if realtime else None
            congestion_label = realtime.get("congestion_label") if realtime else None
            updated_at = realtime.get("updated_at") if realtime else None
            realtime_lines = []
            if weather_label or congestion_label:
                realtime_lines.append(strings["realtime_heading"])
                if weather_label:
                    realtime_lines.append(strings["realtime_weather"].format(label=weather_label))
                if congestion_label:
                    realtime_lines.append(strings["realtime_congestion"].format(label=congestion_label))
                if updated_at:
                    realtime_lines.append(strings["realtime_updated"].format(timestamp=updated_at))
            elif realtime is not None:
                realtime_lines.append(strings["realtime_missing"])
              
            realtime_text = "\n".join(realtime_lines) + "\n" if realtime_lines else ""

            # spot_idから説明ファイル（.md）のパスを構築（lang優先、無ければjaをフォールバック）
            md_candidates = [
                knowledge_base / normalized_lang / "faci_spot" / f"{spot_id}.md",
                knowledge_base / "ja" / "faci_spot" / f"{spot_id}.md",
            ]
            spot_context = ""
            for md_path in md_candidates:
                if md_path.exists():
                    try:
                        spot_context = md_path.read_text(encoding="utf-8")
                        break
                    except Exception as exc:
                        print(f"[WARN] Failed to read Markdown file {md_path}: {exc}")
            if not spot_context:
                spot_context = short_desc or strings["no_detail_fallback"]
                print(f"[WARN] Markdown file not found for spot_id={spot_id} (checked {md_candidates})")

            safe_context = spot_context.replace("\\", "\\\\")
            reason_text = ", ".join(reasons) if reasons else "details"
            summary_text = short_desc or strings["summary_fallback"]
            reco_texts.append(
                strings["recommendation_template"].format(
                    index=i,
                    spot_name=spot_name,
                    reason_text=reason_text,
                    summary=summary_text,
                    realtime_text=realtime_text,
                    context=safe_context,
                )
            )
        
        reco_section = "\n" + strings["recommendation_section_title"] + "\n" + "\n".join(reco_texts)
        instruction = strings["recommendation_instruction"]
        return base_prompt + reco_section + f"\n\n{strings['instruction_heading']}\n{instruction}"

    # 推薦がない場合（雑談など）
    else:
        instruction = strings["chitchat_instruction"]
        return base_prompt + f"\n\n{strings['instruction_heading']}\n{instruction}"
@lru_cache(maxsize=1)
def _load_spot_info_map() -> Dict[str, Dict[str, Any]]:
    base_dir = Path(__file__).resolve().parent
    spot_info_path = base_dir / "processed" / "spot_info.json"
    with spot_info_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    return {item["spot_id"]: item for item in data}


def _normalize_lang(lang: str) -> str:
    if not lang:
        return "ja"
    return lang.split("-")[0].lower()


def _get_localized_text(payload: Any, lang: str) -> str:
    if not isinstance(payload, dict):
        return ""
    normalized = _normalize_lang(lang)
    candidates = [normalized]
    if normalized != "ja":
        candidates.append("ja")
    if normalized != "en":
        candidates.append("en")
    for key in candidates:
        value = payload.get(key)
        if value:
            return value
    if payload:
        for value in payload.values():
            if value:
                return value
    return ""


def _get_spot_display_name(info_map: Dict[str, Dict[str, Any]], spot_id: str, lang: str) -> str:
    spot_info = info_map.get(spot_id) or {}
    name = _get_localized_text(spot_info.get("official_name", {}), lang)
    if name:
        return name

    aliases = spot_info.get("aliases") or {}
    if isinstance(aliases, dict):
        normalized = _normalize_lang(lang)
        preference = [normalized, "zh", "ja", "en"]
        for key in preference:
            alias_list = aliases.get(key) or []
            for alias in alias_list:
                if alias:
                    return alias
        for alias_list in aliases.values():
            if isinstance(alias_list, list):
                for alias in alias_list:
                    if alias:
                        return alias

    display_name = spot_info.get("name") or spot_info.get("spot_name")
    if isinstance(display_name, str) and display_name.strip():
        return display_name
    return spot_id


def _get_label(lang: str, ja_label: str, en_label: str) -> str:
    normalized = _normalize_lang(lang)
    if normalized == "en":
        return en_label
    return ja_label
