from __future__ import annotations

from typing import List, Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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
    lat: float
    lon: float
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

@app.post("/route", response_model=RouteResponse)
def route(payload: RouteRequest):
    if len(payload.waypoints) < 1:
        raise HTTPException(status_code=400, detail="waypoints must be >= 1")
    
    need_resolve = [w.spot_id for w in req.waypoints if w.spot_id and (w.lat is None or w.lon is None)]
    id2coord = SpotRepo.resolve_many(need_resolve) if need_resolve else {}

    resolved: List[Waypoint] = []
    for w in req.waypoints:
        if w.lat is not None and w.lon is not None:
            resolved.append(Waypoint(lat=w.lat, lon=w.lon, spot_id=w.spot_id))
            continue
        if w.spot_id:
            pair = id2coord.get(w.spot_id)
            if not pair:
                raise HTTPException(status_code=400, detail=f"spot_id not found: {w.spot_id}")
            lon, lat = pair
            resolved.append(Waypoint(lat=lat, lon=lon, spot_id=w.spot_id))
            continue
        # ここに来るのは「spot_id も lat/lon も無い」
        raise HTTPException(status_code=400, detail="waypoint must have spot_id or lat/lon")

    # 2) 以降は従来処理：car直行 or car→AP→foot のレッグ構築→GeoJSON化
    try:
        # logic.build_legs_with_switch: List[tuple[lat,lon]] を受け取る前提
        legs = logic.build_legs_with_switch(
            waypoints=[(wp.lat, wp.lon) for wp in resolved],
            car_to_trailhead=req.car_to_trailhead
        )
        fc, polyline, segments = logic.stitch_to_geojson(legs)
        return RouteResponse(
            feature_collection=fc,
            legs=legs,
            polyline=polyline,
            segments=segments
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
