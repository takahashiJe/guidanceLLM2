from __future__ import annotations

import os
from typing import List, Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

# logic モジュールは後で実装（integration テストで monkeypatch 前提）
from backend.worker.app.services.routing import logic as rlogic
from backend.worker.app.services.routing.spot_repo import SpotRepo

app = FastAPI(title="routing service")

class IncomingWaypoint(BaseModel):
    spot_id: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    @field_validator("spot_id", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        return v or None

class Waypoint(BaseModel):
    spot_id: Optional[str] = None

class RouteRequest(BaseModel):
    waypoints: List[Waypoint]
    car_to_trailhead: bool = True

class Leg(BaseModel):
    mode: Literal["car", "foot"]
    from_idx: int
    to_idx: int
    distance: float
    duration: float
    geometry: dict

class Segment(BaseModel):
    mode: Literal["car","foot"]
    start_idx: int
    end_idx: int

class RouteResponse(BaseModel):
    feature_collection: dict
    legs: List[Leg]
    polyline: List[list[float]]
    segments: List[Segment]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/route")
def route(req: RouteRequest) -> RouteResponse:
    """
    前提：
      - req.waypoints は spot_id のみを持つ（lat/lon は来ない）
      - routing 内で spot_id → (lat, lon) を解決し、OSRM に渡す
      - 'current' のような動的 ID は upstream（nav）で座標化してから渡すべきなので routing では 400
    返却：
      - feature_collection / legs / polyline / segments を満たす RouteResponse
    """

    # 0) バリデーション（最低 2 点必要）
    if not req.waypoints or len(req.waypoints) < 2:
        raise HTTPException(status_code=400, detail="At least two waypoints are required.")

    # 1) 動的 ID（現在地など）は routing では扱えない
    dynamic_ids = [wp.spot_id for wp in req.waypoints if (wp.spot_id or "").lower() in {"current", "here", "me"}]
    if dynamic_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Dynamic spot_id {dynamic_ids} cannot be resolved in routing. Resolve to lat/lon upstream."
        )

    # 2) DB 接続情報（ENV）
    db_cfg = dict(
        host=os.getenv("STATIC_DB_HOST", "localhost"),
        port=int(os.getenv("STATIC_DB_PORT", "5432")),
        db=os.getenv("STATIC_DB_NAME", "static_db"),
        user=os.getenv("STATIC_DB_USER", "static_db"),
        password=os.getenv("STATIC_DB_PASSWORD", "static_db"),
    )

    # 3) spot_id → (lat, lon) 解決（順序保持）
    spot_ids = [wp.spot_id for wp in req.waypoints]
    if any(not sid for sid in spot_ids):
        raise HTTPException(status_code=400, detail="All waypoints must contain a non-empty spot_id.")

    repo = SpotRepo(**db_cfg)
    try:
        latlon_list = repo.resolve_spot_ids_to_latlon(spot_ids)  # -> List[Tuple[float, float]]
    except KeyError as e:
        # どの ID が見つからなかったかを明示
        raise HTTPException(status_code=404, detail=f"spot_id not found: {str(e)}")

    # 念のため None を弾く
    if any(ll is None or len(ll) != 2 for ll in latlon_list):
        raise HTTPException(status_code=500, detail="Failed to resolve one or more spot_ids to coordinates.")

    # 4) OSRM ルーティング実行
    osrm = OSRMClient.from_env()  # 例：OSRM エンドポイントは ENV から
    # 期待：route() が [(lat, lon), ...], car_to_trailhead=bool を受け取り dict を返す
    osrm_result = osrm.route(
        coordinates=latlon_list,
        car_to_trailhead=getattr(req, "car_to_trailhead", True)  # 互換のため
    )

    if not osrm_result:
        raise HTTPException(status_code=502, detail="OSRM returned empty response.")

    # 5) 返却整形
    # 既に osrm_result が下記キーを持つならそのまま注入
    expected_keys = {"feature_collection", "legs", "polyline", "segments"}
    if expected_keys.issubset(osrm_result.keys()):
        return RouteResponse(
            feature_collection=osrm_result["feature_collection"],
            legs=osrm_result["legs"],
            polyline=osrm_result["polyline"],
            segments=osrm_result.get("segments", []),
        )

    # あるいは専用ビルダで組み立て（サービス実装に合わせて）
    # return build_route_response(osrm_result)

    # 想定外の形なら 500
    raise HTTPException(status_code=500, detail="Unexpected OSRM response shape.")