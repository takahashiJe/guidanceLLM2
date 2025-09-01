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


@router.post("/plan", response_model=TaskAccepted, status_code=status.HTTP_202_ACCEPTED)
def enqueue_nav_plan(req: NavPlanRequest, request: Request):
    # nav.plan タスクを投入（nav サービス側で定義済み）
    async_res = celery_app.send_task("nav.plan", args=[req.model_dump()])

    # Location: GET で参照できるURLを返す（推奨）
    task_url = request.url_for("get_nav_plan_task", task_id=async_res.id)
    headers = {"Location": str(task_url), "Cache-Control": "no-store"}

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        headers=headers,
        content=TaskAccepted(task_id=async_res.id).model_dump(),
    )

@router.get("/nav/plan/tasks/{task_id}", response_model=TaskStatus, name="get_nav_plan_task")
def get_nav_plan_task(task_id: str):
    res = AsyncResult(task_id, app=celery_app)
    state = res.state

    if state in (states.PENDING, states.RECEIVED, states.STARTED, states.RETRY):
        # まだ完了していない → 202 Accepted
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Cache-Control": "no-store"},
            content=TaskStatus(task_id=task_id, state=state, ready=False).model_dump(),
        )

    if state == states.SUCCESS:
        # 完了 → nav.plan の結果（= 既存 /plan のレスポンスと同一スキーマ）
        result = res.result  # dict のはず（JSONシリアライズ済み）
        if not isinstance(result, dict):
            # 想定外：dict 以外ならサーバエラー扱い
            raise HTTPException(status_code=500, detail="invalid task result")
        return TaskStatus(task_id=task_id, state=state, ready=True, result=result)

    # 失敗 / REVOKED など
    # Celery は res.traceback 等も持つが、外部には詳細を出しすぎない
    raise HTTPException(status_code=500, detail=f"task {state.lower()}")

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
        timeout = httpx.Timeout(connect=3.0, read=180.0, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
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

    return resp.json()
