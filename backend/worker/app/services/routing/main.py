from __future__ import annotations

from typing import List, Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# logic モジュールは後で実装（integration テストで monkeypatch 前提）
from backend.worker.app.services.routing import logic as rlogic

app = FastAPI(title="routing service")

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
    if len(payload.waypoints) < 2:
        raise HTTPException(status_code=400, detail="waypoints must be >= 2")

    legs = rlogic.build_legs_with_switch([(w.lat, w.lon) for w in payload.waypoints])
    fc, polyline, segments = rlogic.stitch_to_geojson(legs)
    return RouteResponse(
        feature_collection=fc,
        legs=legs,  # Leg 型と互換の dict 群を想定
        polyline=polyline,
        segments=segments,
    )
