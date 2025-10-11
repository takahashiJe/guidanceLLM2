
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

@celery_app.task(name="llm.describe", queue="generation")
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
        logger.info(f"LLM raw output for spot {s.spot_id}: {raw_text}")

        # 抽出関数を通してクリーンアップする
        narration_text = _extract_narration(raw_text)
        logger.info(f"LLM cleaned narration for spot {s.spot_id}: {narration_text}")
        
        items.append(DescribeItem(
            spot_id=s.spot_id,
            playback=s.playback,
            situation=s.situation,
            text=narration_text
        ))
    
    response = DescribeResponse(items=items)
    return response.model_dump()
