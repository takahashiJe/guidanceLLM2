from __future__ import annotations

import os
import httpx
from fastapi import APIRouter, HTTPException, status

from backend.api.schemas import ChatRequest, ChatResponse

AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://svc-agent:9200")
REQUEST_TIMEOUT = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "180"))

router = APIRouter(prefix="/v1", tags=["AI Agent"])


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def handle_chat(request: ChatRequest) -> ChatResponse:
    """
    フロントエンドからのチャットリクエストを受け付け、
    内部のAIエージェントサービスを呼び出す。
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AGENT_SERVICE_URL}/invoke",
                json=request.model_dump(),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return ChatResponse(**response.json())
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to AI Agent service: {exc}",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"AI Agent service returned an error: {exc.response.text}",
        ) from exc
