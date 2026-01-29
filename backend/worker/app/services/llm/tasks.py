
from __future__ import annotations

import re
from typing import List, Literal, Optional
from pydantic import BaseModel

from backend.worker.celery_app import celery_app
from backend.worker.app.services.llm import generator, prompt
import logging
logger = logging.getLogger(__name__)


class SpotRef(BaseModel):
    spot_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    md_slug: Optional[str] = None
    playback: Optional[Literal["arrival", "pass_by"]] = None
    situation: Optional[Literal["weather_1","weather_2","congestion_1","congestion_2"]] = None

class DescribeJob(BaseModel):
    job_id: str
    spot: SpotRef

class DescribeRequest(BaseModel):
    language: Literal["ja","en","zh"]
    jobs: List[DescribeJob]

class DescribeItem(BaseModel):
    job_id: Optional[str] = None
    spot_id: str
    playback: Optional[Literal["arrival", "pass_by"]] = None
    situation: Optional[Literal["weather_1","weather_2","congestion_1","congestion_2"]] = None
    text: str

class DescribeResponse(BaseModel):
    items: List[DescribeItem]

def _extract_narration(raw_text: str) -> str:
    """
    LLMが生成した <think>...</think> ブロックを除去し、
    その後に続く本番のナレーションテキストのみを抽出する。
    さらに、LLMがエコーバックするプロンプトの定型文も除去する。
    """
    clean_text = raw_text

    # 1. <think> タグを除去 (複数行モード re.DOTALL を使用)
    clean_text = re.sub(r"<think>.*?</think>", "", clean_text, flags=re.DOTALL)

    # 2. プロンプトの定型文を除去
    # 各行の先頭からマッチさせるため、re.MULTILINE フラグを使用
    patterns_to_remove = [
        # LLM unavailable の行やデバッグ情報
        r"^\[LLM unavailable\].*?日本語\]\s*",
        # ツアーガイドのペルソナ設定
        r"^あなたは鳥海山エリアを訪れる観光客向けのプロのツアーガイドです。\s*",
        # 音声案内作成の指示
        r"^スポット「.*?」の現在の状況を伝える、簡潔な音声案内を作成してください。\s*",
        # スポット名と現在の状況のプレフィックス (ナレーション本体と区別するため)
        r"^スポット名: .*?\s*",
        r"^現在の状況: .*?\s*",
    ]

    for pattern in patterns_to_remove:
        clean_text = re.sub(pattern, "", clean_text, flags=re.MULTILINE | re.DOTALL)
    
    # 残ったテキストの先頭と末尾の空白（改行含む）を除去
    return clean_text.strip()

@celery_app.task(name="llm.describe_job", queue="generation")
def describe_job(payload: dict) -> dict:
    """
    単一スポットの説明文を生成するCeleryタスク。
    payload には {"spot": SpotRef dict, "language": "ja"} の形で渡す。
    """
    if "spot" not in payload or "language" not in payload or "job_id" not in payload:
        raise ValueError("payload must include 'job_id', 'spot' and 'language'")

    spot = SpotRef(**payload["spot"])
    language = payload["language"]
    job_id = payload["job_id"]

    logger.debug(f"[{job_id}] Describing spot: {spot.spot_id}, situation={spot.situation}")
    ctx = generator.retrieve_context(spot.model_dump(), language)
    ptxt = prompt.build_prompt(spot.model_dump(), ctx, language)

    raw_text = generator.generate_text(ptxt)
    logger.info(f"[{job_id}] LLM raw output for spot {spot.spot_id}: {raw_text}")

    narration_text = _extract_narration(raw_text)
    logger.info(f"[{job_id}] LLM cleaned narration for spot {spot.spot_id}: {narration_text}")

    item = DescribeItem(
        job_id=job_id,
        spot_id=spot.spot_id,
        playback=spot.playback,
        situation=spot.situation,
        text=narration_text,
    )
    return item.model_dump()
