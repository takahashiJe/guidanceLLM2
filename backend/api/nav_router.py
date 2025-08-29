from __future__ import annotations

import os
import uuid
from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException, Request

from backend.api.schemas import PlanRequest, PlanResponse

router = APIRouter(prefix="/nav", tags=["navigation"])

NAV_BASE = os.getenv("NAV_BASE", "http://svc-nav:9101")
REQ_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))


def _request_id(headers) -> str:
    return headers.get("x-request-id") or str(uuid.uuid4())


def _model_to_json(m) -> Dict[str, Any]:
    """
    pydantic v1/v2 両対応で dict を取り出す小ヘルパ。
    """
    if hasattr(m, "model_dump"):
        return m.model_dump(by_alias=True)  # pydantic v2
    return m.dict(by_alias=True)            # pydantic v1


@router.post("/plan", response_model=PlanResponse)
async def api_nav_plan(req: PlanRequest, request: Request) -> PlanResponse:
    """
    Frontend からは Nginx のリバプロにより /api/nav/plan で到達。
    ここでは /nav/plan として公開し、/api はNginx側のpath prefixで付与される想定。
    """
    url = f"{NAV_BASE.rstrip('/')}/plan"
    xrid = _request_id(request.headers)
    headers = {"x-request-id": xrid, "content-type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=REQ_TIMEOUT) as client:
            resp = await client.post(url, json=_model_to_json(req), headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="nav service timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"nav service unreachable: {e!s}")

    if resp.status_code != 200:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail={"nav_error": detail})

    data = resp.json()
    return PlanResponse.model_validate(data) if hasattr(PlanResponse, "model_validate") else PlanResponse.parse_obj(data)
