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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/describe", response_model=DescribeResponse)
def describe(payload: DescribeRequest):
    items: list[DescribeItem] = []
    for s in payload.spots:
        ctx = generator.retrieve_context(s.spot_id, payload.language)
        ptxt = prompt.build_prompt(s.model_dump(), ctx, payload.language, payload.style)
        text = generator.generate_text(ptxt)
        items.append(DescribeItem(spot_id=s.spot_id, text=text))
    return DescribeResponse(items=items)
