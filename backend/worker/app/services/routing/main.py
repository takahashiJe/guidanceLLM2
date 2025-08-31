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
    入力: RouteRequest
      - waypoints: List[Waypoint]   # Waypoint は spot_id のみ
      - car_to_trailhead: bool = True

    処理:
      1) spot_id 群を DB で (lon,lat) に解決（順序を保って再構成）
      2) (lon,lat) → (lat,lon) に変換して routing ロジックへ
      3) OSRM を叩いて legs を構築
      4) GeoJSON / polyline / segments を組み立てて返却

    出力: RouteResponse
      - feature_collection / legs / polyline / segments
    """

    # 0) バリデーション
    if not req.waypoints or len(req.waypoints) < 2:
        raise HTTPException(status_code=400, detail="At least two waypoints are required.")

    spot_ids = []
    for i, wp in enumerate(req.waypoints):
        sid = (wp.spot_id or "").strip() if hasattr(wp, "spot_id") else ""
        if not sid:
            raise HTTPException(status_code=400, detail=f"waypoints[{i}] must have a non-empty spot_id.")
        # 'current' 等の動的 ID は routing では扱わない（nav 側で座標に置換してから渡す）
        if sid.lower() in {"current", "here", "me"}:
            raise HTTPException(status_code=400, detail=f"Dynamic spot_id '{sid}' must be resolved upstream.")
        spot_ids.append(sid)

    # 1) spot_id → (lon,lat) を解決
    repo = SpotRepo()  # 引数なしでOK（ENVはspot_repo内で読む）
    id2lonlat = repo.resolve_many(spot_ids)  # Dict[str, Tuple[float, float]]  ※(lon,lat)

    # 見つからない ID を検出
    missing = [sid for sid in spot_ids if sid not in id2lonlat]
    if missing:
        raise HTTPException(status_code=404, detail=f"spot_id not found in DB: {missing}")

    # 2) (lon,lat) → (lat,lon) に変換（順序を保つ）
    waypoints_latlon: List[tuple[float, float]] = []
    for sid in spot_ids:
        lon, lat = id2lonlat[sid]
        waypoints_latlon.append((lat, lon))  # logic/osrm は (lat,lon) 想定

    # 3) ルート構築（car→trailhead スイッチ含む）
    #    logic.build_legs_with_switch は:
    #    - 引数: List[tuple[lat,lon]]
    #    - 戻り: List[dict] (mode, from_idx, to_idx, distance, duration, geometry)
    legs = build_legs_with_switch(waypoints_latlon)

    # 4) GeoJSON / polyline / segments 生成
    feature_collection, polyline, segments = stitch_to_geojson(legs)

    return RouteResponse(
        feature_collection=feature_collection,
        legs=legs,
        polyline=polyline,
        segments=segments,
    )