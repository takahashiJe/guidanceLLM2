from __future__ import annotations

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

def describe_impl(payload: DescribeRequest) -> DescribeResponse:
    items: list[DescribeItem] = []
    for s in payload.spots:
        # 既存処理：コンテキスト収集 → プロンプト生成 → LLM生成
        ctx = generator.retrieve_context(s.spot_id, payload.language)
        ptxt = prompt.build_prompt(s.model_dump(), ctx, payload.language, payload.style)
        text = generator.generate_text(ptxt)
        items.append(DescribeItem(spot_id=s.spot_id, text=text))
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