from __future__ import annotations

from typing import List, Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.worker.app.services.alongpoi import geo_ops
from backend.worker.app.services.alongpoi import reducer
from backend.worker.app.services.alongpoi import poi_repo

app = FastAPI(title="alongpoi service")

class Segment(BaseModel):
    mode: Literal["car","foot"]
    start_idx: int
    end_idx: int

class AlongRequest(BaseModel):
    polyline: List[List[float]]   # [[lon,lat], ...]
    segments: List[Segment]
    buffer: dict = Field(default_factory=lambda: {"car":300,"foot":10})

class AlongResponse(BaseModel):
    pois: List[dict]
    count: int

@app.get("/health")
def health():
    return {"status": "ok"}

# 分離しておく（integration テストで monkeypatch される）
def query_pois_in_buffers(polys) -> list[dict]:
    return poi_repo.query_pois(polys)

@app.post("/along", response_model=AlongResponse)
def along(payload: AlongRequest):
    if not payload.polyline:
        raise HTTPException(status_code=400, detail="polyline required")

    lines = geo_ops.build_mode_multilines(
    payload.polyline,
    [s.model_dump() for s in payload.segments],
    )
    hits = poi_repo.query_pois_near_route(
        lines,
        car_m = payload.buffer.get("car", 300.0),
        foot_m = payload.buffer.get("foot", 10.0),
    )
    pois = reducer.reduce_hits_to_along_pois(hits, payload.polyline)
