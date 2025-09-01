from __future__ import annotations

import os
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Literal, Optional, Dict
from hashlib import sha1

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.worker.app.services.nav.client_routing import post_route
from backend.worker.app.services.nav.client_alongpoi import post_along
from backend.worker.app.services.nav.client_llm import post_describe
from backend.worker.app.services.nav.client_voice import post_synthesize
from backend.worker.app.services.nav.spot_repo import get_spots_by_ids

app = FastAPI(title="nav service")

# ==== Schemas ====
class Waypoint(BaseModel):
    spot_id: Optional[str] = None

class Coord(BaseModel):
    lat: float
    lon: float

class PlanRequest(BaseModel):
    language: Literal["ja", "en", "zh"]
    origin: Coord
    waypoints: List[Waypoint]
    buffer: dict = Field(default_factory=lambda: {"car": 300, "foot": 10})

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
    format: Optional[Literal["mp3","wav"]] = None

class PlanResponse(BaseModel):
    pack_id: str
    route: dict
    legs: List[Leg]
    along_pois: List[dict]
    assets: List[Asset]

# ==== Helpers ====
def _collect_unique_spot_ids(waypoints: List[Waypoint], along_pois: List[dict]) -> List[str]:
    planned = [w.spot_id for w in waypoints if w.spot_id and w.spot_id != "current"]
    along = [p.get("spot_id") for p in along_pois if p.get("spot_id")]
    uniq: List[str] = []
    seen = set()
    for sid in planned + along:
        if sid not in seen:
            seen.add(sid)
            uniq.append(sid)
    return uniq

def _build_spot_refs(spot_ids: List[str]) -> List[dict]:
    """
    spots テーブルから name/description/md_slug を解決し、
    LLM へ渡す SpotRef（dict）に整形。
    """
    refmap = get_spots_by_ids(spot_ids)  # {id: SpotRow}
    items: List[dict] = []
    for sid in spot_ids:
        row = refmap.get(sid)
        if row:
            items.append(
                {
                    "spot_id": sid,
                    "name": row.name,
                    "description": row.description,
                    "md_slug": row.md_slug,
                    "lat": lat,
                    "lon": lon,
                }
            )
        else:
            # DB から取れなくても最低限 spot_id だけ渡す
            items.append({"spot_id": sid})
    return items

# ==== Endpoints ====
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
    routing_req = {
        "origin": payload.origin.model_dump(),  # origin を追加
        "waypoints": [w.model_dump() for w in payload.waypoints],
        "car_to_trailhead": True
        }
    routing = post_route(routing_req)
    print(f"post_route return keys: {list(routing.keys())}")
    print(f"post_route return full content: {json.dumps(routing, ensure_ascii=False, indent=2)}")
    route_fc = routing["feature_collection"]
    legs_from_routing = routing["legs"]
    print(f"legs_from_routing: {legs_from_routing}")
    polyline = routing["polyline"]
    segments = routing.get("segments", [])
    spot_id_to_coords = {s.spot_id: (s.lat, s.lon) for s in get_spots_by_ids([w.spot_id for w in payload.waypoints])}
    coords_list = [
        (payload.origin.lat, payload.origin.lon)
    ]
    for wp in payload.waypoints:
        if wp.spot_id in spot_id_to_coords:
            coords_list.append(spot_id_to_coords[wp.spot_id])
    coords_list.append((payload.origin.lat, payload.origin.lon))

    # APIスキーマに合わせた legs を生成
    final_legs = []
    for leg_data in legs_from_routing:
        from_coords = coords_list[leg_data["from_idx"]]
        to_coords = coords_list[leg_data["to_idx"]]
        final_legs.append({
            "mode": leg_data["mode"],
            "from": {"lat": from_coords[0], "lon": from_coords[1]},
            "to": {"lat": to_coords[0], "lon": to_coords[1]},
            "distance_m": leg_data["distance"],
            "duration_s": leg_data["duration"]
        })

    # 2) alongpoi
    along_req = {"polyline": polyline, "segments": segments, "buffer": payload.buffer}
    along = post_along(along_req)
    along_pois = along.get("pois", [])

    # 3) LLM: planned + along をユニーク化し、spots テーブルで name/description/md_slug を解決
    uniq_ids = _collect_unique_spot_ids(payload.waypoints, along_pois)
    spot_refs = _build_spot_refs(uniq_ids)
    llm_req = {"language": payload.language, "style": "narration", "spots": spot_refs}
    llm_out = post_describe(llm_req)  # {"items":[{"spot_id","text"}]}

    # 4) voice TTS（並列化は後続タスクで。まずは逐次でOK）
    voice_format = os.getenv("VOICE_FORMAT", "mp3")
    voice_bitrate = int(os.getenv("VOICE_BITRATE_KBPS", "64"))
    save_text = (os.getenv("VOICE_SAVE_TEXT", "1") == "1")
    assets: List[Asset] = []
    for item in llm_out.get("items", []):
        sid = item["spot_id"]
        voice_req = {
            "language": payload.language,
            "voice": "guide_female_1",
            "text": item["text"],
            "spot_id": sid,
            "pack_id": pack_id,
            "format": voice_format,
            "bitrate_kbps": voice_bitrate,
            "save_text": save_text,
        }
        vj = post_synthesize(voice_req)
        assets.append(
            Asset(
                spot_id=sid,
                audio_url=vj.get("audio_url"),
                text_url=vj.get("text_url"),  # 追加（save_text=true時に返る）
                bytes=vj.get("bytes"),
                duration_s=vj.get("duration_s"),
                format=vj.get("format"),   # 任意で格納したい場合のみ
            )
        )

    # manifest を生成
    manifest = {
        "pack_id": pack_id,
        "language": payload.language,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "route_digest": sha1(json.dumps(polyline, separators=(',',':')).encode()).hexdigest(),
        "segments": segments,
        "assets": [asset.model_dump() for asset in assets]
    }
    manifest_path = Path(os.environ.get("PACKS_DIR","/packs"))/pack_id/"manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    manifest_url = f"{os.environ.get('PACKS_BASE_URL','/packs')}/{pack_id}/manifest.json"

    return PlanResponse(
        pack_id=pack_id,
        route=route_fc,
        legs=final_legs,
        along_pois=along_pois,
        assets=assets,
        manifest_url=manifest_url
    )
