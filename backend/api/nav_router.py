from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional, Union
import json

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from celery.result import AsyncResult, GroupResult
from celery import states

from backend.api.celery_app import celery_app
from backend.api.schemas import PlanRequest, PlanResponse

router = APIRouter(prefix="/nav", tags=["navigation"])

NAV_BASE = os.getenv("NAV_BASE", "http://svc-nav:9100")
REQ_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
INCOMPLETE = {states.PENDING, states.RECEIVED, states.STARTED, states.RETRY}

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
def _flatten_children(r: AsyncResult) -> list[AsyncResult]:
    """
    r.children は None / list[AsyncResult] / list[GroupResult] が混在し得る。
    GroupResult は .results で展開する。
    """
    out: list[AsyncResult] = []
    ch = getattr(r, "children", None) or []
    for c in ch:
        if isinstance(c, GroupResult):
            out.extend(c.results or [])
        else:
            out.append(c)
    return out

def _deepest_descendant(r: AsyncResult) -> AsyncResult:
    """
    タスクチェーンを辿り、最終的な葉（leaf）タスクの結果オブジェクトを返す。
    r.children は chord を使うと意図通りに動かないため、
    より堅牢な r.parent を遡る方式に変更。
    """
    # まず、現在完了している一番深い子孫を探す
    curr = r
    seen = {curr.id}
    for _ in range(20): # 安全のためのループ制限
        if not curr.children:
            break

        # GroupResultは展開せず、そのまま子として扱う
        children = curr.children
        if not children:
            break

        next_task_result = children[0]
        if next_task_result.id in seen:
            break

        curr = next_task_result
        seen.add(curr.id)

    # そこから、状態がSUCCESSになるまで親を遡る
    # (chordの完了を待つため)
    final_task = curr
    for _ in range(20): # 安全のためのループ制限
        if final_task.state == states.SUCCESS:
            break
        if not final_task.parent:
            break
        if final_task.parent.id in seen:
            break

        final_task = final_task.parent
        seen.add(final_task.id)

    return final_task

def _as_dict_if_json_string(x: Union[str, dict]) -> Union[dict, None]:
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            v = json.loads(x)
            return v if isinstance(v, dict) else None
        except Exception:
            return None
    return None

@router.get("/plan/tasks/{task_id}", name="get_nav_plan_task")
def get_nav_plan_task(task_id: str):
    """
    ポーリング: 親(nav.plan)のIDでもOK。チェインの末端(finalize)までフォローして結果(dict)を返す。
    未完了なら 202、成功なら 200 + PlanResponse、失敗なら 500。
    """
    root = AsyncResult(task_id, app=celery_app)

    # 1) 未完了なら 202
    if root.state in INCOMPLETE:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            headers={"Cache-Control": "no-store"},
            content={"task_id": task_id, "state": root.state, "ready": False},
        )

    # 2) SUCCESS だが result が dict でないケースに備える
    #    - nav.plan がチェインを投げっぱなし→自分の result が None
    #    - JSON文字列で返ってきた
    raw = root.result
    doc = _as_dict_if_json_string(raw)

    if doc is None:
        # FINALIZE（チェインの末端）を辿ってそこから結果を取得
        leaf = _deepest_descendant(root)

        if leaf.id != root.id:
            # 末端の状態で再判定
            if leaf.state in INCOMPLETE:
                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    headers={"Cache-Control": "no-store"},
                    content={"task_id": task_id, "state": leaf.state, "ready": False},
                )
            if leaf.state == states.FAILURE:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "task_id": task_id,
                        "state": leaf.state,
                        "ready": False,
                        "error": str(leaf.info),
                        "traceback": leaf.traceback,
                    },
                )
            # leaf SUCCESS の場合に dict or JSON文字列かを評価
            doc = _as_dict_if_json_string(leaf.result)

    if doc is None:
        # ここまで来て dict にならない＝タスク側の戻り値が不正
        raise HTTPException(status_code=500, detail="task returned empty or invalid result")

    # 3) スキーマ検証 → 200で返す（alias考慮）
    try:
        pr = PlanResponse(**doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"invalid nav.plan result: {e}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=pr.model_dump(by_alias=True),
    )