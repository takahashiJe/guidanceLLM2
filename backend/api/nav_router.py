from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from celery.result import AsyncResult
from celery import states

from backend.api.celery_app import celery_app
from backend.api.schemas import PlanRequest, PlanResponse

router = APIRouter(prefix="/nav", tags=["navigation"])

NAV_BASE = os.getenv("NAV_BASE", "http://svc-nav:9100")
REQ_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))

class TaskAccepted(BaseModel):
    task_id: str
    status: str = "accepted"

class TaskStatus(BaseModel):
    task_id: str
    state: str
    ready: bool

def _request_id(headers) -> str:
    return headers.get("x-request-id") or str(uuid.uuid4())


def _model_to_json(m) -> Dict[str, Any]:
    """
    pydantic v1/v2 両対応で dict を取り出す小ヘルパ。
    """
    if hasattr(m, "model_dump"):
        return m.model_dump(by_alias=True)  # pydantic v2
    return m.dict(by_alias=True)            # pydantic v1


# ========== GET /api/nav/plan/tasks/{task_id} → 状態照会 ==========
@router.get("/nav/plan/tasks/{task_id}", name="get_nav_plan_task")
def get_nav_plan_task(task_id: str):
    res = AsyncResult(task_id, app=celery_app)
    state = res.state

    # 未完了 → 202
    if state in (states.PENDING, states.RECEIVED, states.STARTED, states.RETRY):
        body = TaskStatus(task_id=task_id, state=state, ready=False).model_dump()
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Cache-Control": "no-store"},
            content=body,
        )

    # 成功 → 200 + PlanResponse
    if state == states.SUCCESS:
        raw: Dict[str, Any] = res.result  # nav.plan の戻り（dictの想定）
        try:
            pr = PlanResponse(**raw)  # schemas.py で検証
        except ValidationError as e:
            raise HTTPException(status_code=500, detail=f"invalid nav.plan result: {e.errors()}")
        # alias（Leg.from_ → "from"）で返す
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=pr.model_dump(by_alias=True),
        )

    # 失敗など → 500
    raise HTTPException(status_code=500, detail=f"task {state.lower()}")