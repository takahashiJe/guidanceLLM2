from __future__ import annotations

import os
import uuid
from typing import List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROUTING_BASE = os.getenv("ROUTING_BASE", "http://svc-routing:9101")
ALONGPOI_BASE = os.getenv("ALONGPOI_BASE", "http://svc-alongpoi:9102")
LLM_BASE = os.getenv("LLM_BASE", "http://svc-llm:9103")
VOICE_BASE = os.getenv("VOICE_BASE", "http://svc-voice:9104")

app = FastAPI(title="nav service")

# ---- Schemas ----
class Waypoint(BaseModel):
    lat: float
    lon: float
    spot_id: Optional[str] = None

class PlanRequest(BaseModel):
    language: Literal["ja", "en", "zh"]
    waypoints: List[Waypoint]
    buffers: dict = Field(default_factory=lambda: {"car": 300, "foot": 10})

class Leg(BaseModel):
    mode: Literal["car", "foot"]
    from_idx: int
    to_idx: int
    distance: float
    duration: float

class Asset(BaseModel):
    spot_id: str
    audio_url: Optional[str] = None
    text_url: Optional[str] = None
    bytes: Optional[int] = None
    duration_s: Optional[float] = None

class PlanResponse(BaseModel):
    pack_id: str
    route: dict
    legs: List[Leg]
    along_pois: List[dict]
    assets: List[Asset]

# ---- Endpoints ----
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.post("/plan", response_model=PlanResponse)
def plan(payload: PlanRequest):
    if len(payload.waypoints) < 2:
        raise HTTPException(status_code=400, detail="waypoints must be >= 2")

    pack_id = str(uuid.uuid4())

    # 1) routing
    routing_req = {"waypoints": [w.model_dump() for w in payload.waypoints], "car_to_trailhead": True}
    with httpx.Client(timeout=30) as client:
        r1 = client.post(f"{ROUTING_BASE}/route", json=routing_req)
    if r1.status_code != 200:
        raise HTTPException(status_code=502, detail=f"routing error: {r1.text}")
    routing = r1.json()
    route_fc = routing["feature_collection"]
    legs = routing["legs"]
    polyline = routing["polyline"]
    segments = routing.get("segments", [])

    # 2) alongpoi
    along_req = {"polyline": polyline, "segments": segments, "buffer": payload.buffers}
    with httpx.Client(timeout=30) as client:
        r2 = client.post(f"{ALONGPOI_BASE}/along", json=along_req)
    if r2.status_code != 200:
        raise HTTPException(status_code=502, detail=f"alongpoi error: {r2.text}")
    along = r2.json()
    along_pois = along.get("pois", [])

    # 3) LLM（説明テキスト生成）— テキストURLは後で付与（任意）
    #    入力スポット：訪問予定（current 以外）＋沿道
    planned_spots = [w for w in payload.waypoints if (w.spot_id and w.spot_id != "current")]
    planned_ids = [w.spot_id for w in planned_spots]
    along_ids = [p["spot_id"] for p in along_pois]
    unique_ids = []
    seen = set()
    for sid in planned_ids + along_ids:
        if sid and sid not in seen:
            seen.add(sid)
            unique_ids.append(sid)
    llm_req = {"language": payload.language, "style": "narration", "spots": [{"spot_id": sid} for sid in unique_ids]}
    with httpx.Client(timeout=60) as client:
        r3 = client.post(f"{LLM_BASE}/describe", json=llm_req)
    if r3.status_code != 200:
        raise HTTPException(status_code=502, detail=f"llm error: {r3.text}")
    llm_out = r3.json()  # {"items":[{"spot_id","text"}]}

    # 4) voice（TTS）
    assets: list[Asset] = []
    with httpx.Client(timeout=60) as client:
        for item in llm_out.get("items", []):
            sid = item["spot_id"]
            # 説明テキストの保存と text_url 生成は後続の実装で．ここでは音声のみ必須．
            voice_req = {
                "language": payload.language,
                "voice": "guide_female_1",
                "text": item["text"],
                "spot_id": sid,
                "pack_id": pack_id,
            }
            rv = client.post(f"{VOICE_BASE}/synthesize", json=voice_req)
            if rv.status_code != 200:
                # 音声生成に失敗しても他は継続（必要に応じて仕様変更）
                continue
            vj = rv.json()
            assets.append(Asset(spot_id=sid, audio_url=vj.get("audio_url"), bytes=vj.get("bytes"), duration_s=vj.get("duration_s")))

    return PlanResponse(
        pack_id=pack_id,
        route=route_fc,
        legs=[Leg(**l) for l in legs],
        along_pois=along_pois,
        assets=assets,
    )
