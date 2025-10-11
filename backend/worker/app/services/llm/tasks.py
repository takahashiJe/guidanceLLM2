
from __future__ import annotations

import re
from typing import List, Literal, Optional
from pydantic import BaseModel

from backend.worker.app.services.llm.celery_app import celery_app
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

class DescribeRequest(BaseModel):
    language: Literal["ja","en","zh"]
    spots: List[SpotRef]

class DescribeItem(BaseModel):
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
    """
    # <think> タグ（複数行モード re.DOTALL を使用）を除去
    clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
    
    # 残ったテキストの先頭と末尾の空白（改行含む）を除去
    return clean_text.strip()

@celery_app.task(name="llm.describe")
def describe(payload: dict) -> dict:
    """
    LLMでスポットの説明文を生成するCeleryタスク。
    """
    req = DescribeRequest(**payload)
    items: list[DescribeItem] = []
    for s in req.spots:
        logger.debug(f"Describing spot: {s.spot_id}, situation={s.situation}")
        # 既存処理：コンテキスト収集 → プロンプト生成 → LLM生成
        ctx = generator.retrieve_context(s.model_dump(), req.language)
        ptxt = prompt.build_prompt(s.model_dump(), ctx, req.language)

        # generator が生のテキスト(思考タグ含む)を返す
        raw_text = generator.generate_text(ptxt) # generator.py を使用
        # 抽出関数を通してクリーンアップする
        narration_text = _extract_narration(raw_text)
        
        items.append(DescribeItem(
            spot_id=s.spot_id,
            playback=s.playback,
            situation=s.situation,
            text=narration_text
        ))
    
    response = DescribeResponse(items=items)
    return response.model_dump()
