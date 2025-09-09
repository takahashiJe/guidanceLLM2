from __future__ import annotations

import re
from typing import List, Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.worker.app.services.llm import generator, prompt

app = FastAPI(title="llm service")

class SpotRef(BaseModel):
    spot_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    md_slug: Optional[str] = None

class DescribeRequest(BaseModel):
    language: Literal["ja","en","zh"]
    spots: List[SpotRef]
    style: str = "narration"

class DescribeItem(BaseModel):
    spot_id: str
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

def describe_impl(payload: DescribeRequest) -> DescribeResponse:
    items: list[DescribeItem] = []
    for s in payload.spots:
        # 既存処理：コンテキスト収集 → プロンプト生成 → LLM生成
        ctx = generator.retrieve_context(s.spot_id, payload.language)
        ptxt = prompt.build_prompt(s.model_dump(), ctx, payload.language, payload.style)

        # generator が生のテキスト(思考タグ含む)を返す
        raw_text = generator.generate_text(ptxt) # generator.py を使用
        # 抽出関数を通してクリーンアップする
        narration_text = _extract_narration(raw_text)
        
        items.append(DescribeItem(spot_id=s.spot_id, text=narration_text))
    return DescribeResponse(items=items)

@app.post("/describe", response_model=DescribeResponse)
def describe(req: DescribeRequest) -> DescribeResponse:
    """
    LLMでスポットの説明文を生成するエンドポイント。
    入力・出力の形式は元のCeleryタスクと同一。
    """
    # 中核ロジックを呼び出す
    return describe_impl(req)

@app.get("/health")
def health():
    return {"status": "ok"}