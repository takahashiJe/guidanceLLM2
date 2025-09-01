from __future__ import annotations

from typing import List, Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.worker.app.services.llm import generator, prompt
from backend.worker.app.services.llm.celery_app import celery_app

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

@celery_app.task(name="llm.describe", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def describe_task(self, payload: dict) -> dict:
    """
    Celery からは JSON(dict) が渡されるので、Pydantic で復元して同じ処理を実行。
    戻り値も JSON(dict)（DescribeResponse と同じ形）で返す。
    """
    req = DescribeRequest(**payload)
    res = describe_impl(req)
    # Celery の result_serializer='json' に合わせて Python dict にして返す
    return res.model_dump()