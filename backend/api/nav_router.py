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


# ========== POST /api/nav/plan → タスク投入して 202 ==========
@router.post("/plan", response_model=TaskAccepted, status_code=status.HTTP_202_ACCEPTED)
def enqueue_nav_plan(req: PlanRequest, request: Request):
    # nav.plan タスク投入（nav 側で定義済み）
    async_res = celery_app.send_task("nav.plan", args=[req.model_dump(by_alias=True)], queue="nav")

    # Location ヘッダ（GET の参照先）を添付
    task_url = request.url_for("get_nav_plan_task", task_id=async_res.id)
    headers = {"Location": str(task_url), "Cache-Control": "no-store"}

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        headers=headers,
        content=TaskAccepted(task_id=async_res.id).model_dump(),
    )

# ========== GET /api/nav/plan/tasks/{task_id} → 状態照会 ==========
@router.get("/plan/tasks/{task_id}", name="get_nav_plan_task")
def get_nav_plan_task(task_id: str):
    res = AsyncResult(task_id, app=celery_app)
    state = res.state

    if state in (states.PENDING, states.RECEIVED, states.STARTED, states.RETRY):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Cache-Control": "no-store"},
            content={"task_id": task_id, "state": state, "ready": False},
        )

    if state == states.SUCCESS:
        raw = res.result
        if not isinstance(raw, dict):
            raise HTTPException(status_code=500, detail="task returned empty or invalid result")
        try:
            pr = PlanResponse(**raw)  # スキーマ検証
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"invalid nav.plan result: {e}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=pr.model_dump(by_alias=True),
        )

    # 失敗時（FAILURE/REVOKEDなど）
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "task_id": task_id,
            "state": state,
            "ready": False,
            "error": str(res.info),
            "traceback": res.traceback,  # 本番では外してOK
        },
    )