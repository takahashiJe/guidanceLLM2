
from __future__ import annotations

import os
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Literal, Optional, Dict, Any

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request

# 各サービスを呼び出すためのHTTPクライアント
from backend.worker.app.services.nav.client_routing import post_route
from backend.worker.app.services.nav.client_alongpoi import post_along
from backend.worker.app.services.nav.client_llm import post_describe
from backend.worker.app.services.nav.client_voice import post_synthesize_and_save

from backend.worker.app.services.nav.spot_repo import get_spots_by_ids

import logging
logger = logging.getLogger(__name__)

app = FastAPI(title="nav service")

# Schemas from tasks.py
class Coord(BaseModel):
    lat: float
    lon: float

class WaypointInfo(BaseModel):
    spot_id: str
    name: str
    lon: float
    lat: float
    nearest_idx: int
    distance_m: float

class Segment(BaseModel):
    mode: Literal["car", "foot"]
    start_idx: int
    end_idx: int

class PlanRequest(BaseModel):
    language: Literal["ja", "en", "zh"]
    buffer: dict = Field(default_factory=lambda: {"car": 300, "foot": 10})
    route: dict
    polyline: List[List[float]]
    segments: List[Segment]
    legs: List[dict]
    waypoints_info: List[WaypointInfo]
    pack_id: Optional[str] = None # pack_id is now optional

class Asset(BaseModel):
    spot_id: str
    situation: Optional[Literal["weather_1","weather_2","congestion_1","congestion_2"]] = None
    audio_url: Optional[str] = None
    text_url: Optional[str] = None
    bytes: Optional[int] = None
    duration_s: Optional[float] = None
    format: Optional[Literal["mp3","wav"]] = None

class PlanResponse(BaseModel):
    pack_id: str
    along_pois: List[dict]
    assets: List[Asset]
    manifest_url: str

CONDITIONAL_NARRATIONS = {
    "weather_1": "w=1 (Cloudy)",
    "weather_2": "w=2 (Rainy)",
    "congestion_1": "c=1 (Congested)",
    "congestion_2": "c=2 (Full)",
}

# Helper functions from tasks.py
def _collect_unique_spot_ids(waypoints_info: List[WaypointInfo], along_pois: List[dict]) -> List[str]:
    planned = [w.spot_id for w in waypoints_info if w.spot_id and w.spot_id != "current"]
    along = [p.get("spot_id") for p in along_pois if p.get("spot_id")]
    uniq: List[str] = []
    seen = set()
    for sid in planned + along:
        if sid not in seen:
            seen.add(sid)
            uniq.append(sid)
    return uniq

def _build_spot_refs(spot_ids: List[str], language: str) -> List[dict]:
    spot_rows = get_spots_by_ids(spot_ids, language).values()
    items = []
    for row in spot_rows:
        desc = row.description
        if isinstance(desc, dict):
            desc_text = desc.get(language, desc.get("en", ""))
        else:
            desc_text = str(desc or "")

        items.append({
            "spot_id": row.spot_id,
            "name": row.name,
            "description": desc_text,
            "md_slug": row.md_slug,
            "lon": row.lon,
            "lat": row.lat,
        })
    return items


def _idx_to_coord(polyline: list, idx: int) -> dict | None:
    if idx is None or not (0 <= idx < len(polyline)):
        return None
    coord = polyline[idx]
    return {"lat": coord[0], "lon": coord[1]}


def _normalize_legs(raw_legs: list, polyline: list) -> list:
    out = []
    for lg in (raw_legs or []):
        mode = lg.get("mode", "car")
        from_coord = lg.get("from") or lg.get("from_")
        to_coord = lg.get("to")
        if isinstance(from_coord, dict) and "lat" in from_coord and "lon" in from_coord and isinstance(to_coord, dict) and "lat" in to_coord and "lon" in to_coord:
            dist, dur = lg.get("distance_m", lg.get("distance")), lg.get("duration_s", lg.get("duration"))
            out.append({"mode": mode, "from": from_coord, "to": to_coord, "distance_m": float(dist or 0.0), "duration_s": float(dur or 0.0)})
            continue
        fidx, tidx = lg.get("from_idx"), lg.get("to_idx")
        f, t = (_idx_to_coord(polyline, fidx) if fidx is not None else None), (_idx_to_coord(polyline, tidx) if tidx is not None else None)
        dist, dur = lg.get("distance_m", lg.get("distance")), lg.get("duration_s", lg.get("duration"))
        out.append({"mode": mode, "from": f or {"lat": 0.0, "lon": 0.0}, "to": t or {"lat": 0.0, "lon": 0.0}, "distance_m": float(dist or 0.0), "duration_s": float(dur or 0.0)})
    return out

def _normalize_assets(voice_results: list[dict], llm_items: list[dict]) -> list[dict]:
    llm_item_map = {
        (item.get("spot_id"), item.get("situation")): item
        for item in llm_items
    }

    assets = []
    processed_keys = set()

    for vr in voice_results or []:
        sid = vr.get("spot_id")
        ntype = vr.get("situation")
        if not sid:
            continue

        key = (sid, ntype)
        if key in llm_item_map:
            llm_item = llm_item_map[key]
            assets.append({
                "spot_id": sid,
                "situation": ntype,
                "text": llm_item.get("text", ""),
                "audio_url": vr.get("audio_url"),
                "text_url": vr.get("text_url"),
                "bytes": vr.get("bytes"),
                "duration_s": vr.get("duration_s"),
                "format": vr.get("format"),
            })
            processed_keys.add(key)

    for key, item in llm_item_map.items():
        if key not in processed_keys:
            assets.append({
                "spot_id": item.get("spot_id"),
                "situation": item.get("situation"),
                "text": item.get("text", ""),
                "audio_url": None,
                "text_url": None,
                "bytes": None,
                "duration_s": None,
                "format": None,
            })
    return assets

def _write_manifest(pack_id: str, language: str, route_fc: dict, polyline: list, segments: list, legs: list, waypoints_info: list, along_pois: list, assets: list) -> None:
    root = Path(os.getenv("PACKS_ROOT") or "/packs")
    pack_dir = root / pack_id
    try:
        pack_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "pack_id": pack_id, "language": language, "generated_at": datetime.utcnow().isoformat() + "Z",
            "route": route_fc, "polyline_len": len(polyline or []), "segments": segments,
            "legs": legs,
            "waypoints_info": waypoints_info,
            "along_pois": along_pois,
            "assets": assets,
        }
        p = pack_dir / "manifest.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        logger.info("NAV wrote manifest: %s", str(p))
    except Exception:
        logger.exception("NAV failed to write manifest.json for pack_id=%s", pack_id)


@app.post("/plan", response_model=PlanResponse)
def plan_endpoint(req: PlanRequest, request: Request):
    print("--- [svc-nav /plan] ENTERED ENDPOINT. --- ", flush=True)
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    pack_id = req.pack_id or str(uuid.uuid4())
    logger.info(f"[{request_id}] Workflow started for pack_id: {pack_id}")

    # --- AlongPOI Service ---
    logger.info("Step 2: Calling AlongPOI service...")
    waypoint_ids = [wp.spot_id for wp in req.waypoints_info if wp.spot_id and wp.spot_id != "current"]
    along_req = {"polyline": req.polyline, "segments": [s.model_dump() for s in req.segments], "buffer": req.buffer, "waypoints": waypoint_ids}
    print("--- [svc-nav /plan] CALLING ALONGPOI... ---", flush=True)
    along_result = post_along(along_req)
    print("--- [svc-nav /plan] ALONGPOI CALL COMPLETE. --- ", flush=True)
    along_pois = along_result.get("pois", [])
    logger.info(f"AlongPOI service returned {len(along_pois)} POIs.")

    along_spot_id_set = {p.get("spot_id") for p in along_pois if isinstance(p, dict) and p.get("spot_id") and p.get("spot_id") != "current"}

    # --- LLM Service ---
    logger.info("Step 3: Calling LLM service...")
    all_spot_ids = _collect_unique_spot_ids(req.waypoints_info, along_pois)
    spot_refs = _build_spot_refs(all_spot_ids, req.language)

    waypoint_id_set = set(waypoint_ids)
    enhanced_spot_refs: list[dict] = []
    for ref in spot_refs:
        sid = ref.get("spot_id")
        playback = "arrival" if sid in waypoint_id_set else "pass_by"
        if playback == "pass_by" and sid not in along_spot_id_set:
            playback = "arrival"
        enriched = {**ref, "playback": playback}
        enhanced_spot_refs.append(enriched)
    spot_refs = enhanced_spot_refs

    conditional_spot_refs = []
    waypoint_spot_refs = [ref for ref in spot_refs if ref['spot_id'] in waypoint_id_set]

    for spot_ref in waypoint_spot_refs:
        for key in CONDITIONAL_NARRATIONS.keys():
            conditional_ref = spot_ref.copy()
            conditional_ref["situation"] = key
            conditional_spot_refs.append(conditional_ref)

    combined_spots_for_llm = spot_refs + conditional_spot_refs

    llm_items = []
    if combined_spots_for_llm:
        llm_req = {"language": req.language, "spots": combined_spots_for_llm}
        situation_count = sum(1 for s in combined_spots_for_llm if "situation" in s)
        logger.info(f"{situation_count} spots have 'situation' for conditional prompts.")
        llm_result = post_describe(llm_req)
        llm_items = llm_result.get("items", [])
        logger.info(f"LLM service returned {len(llm_items)} descriptions.")
    else:
        logger.info("No spots to describe, skipping LLM service.")

    # --- Voice Service ---
    logger.info("Step 4: Calling Voice service...")
    voice_results = []
    if llm_items:
        voice_req = {
            "pack_id": pack_id,
            "language": req.language,
            "items": llm_items,
            "preferred_format": os.getenv("VOICE_FORMAT", "mp3"),
            "bitrate_kbps": int(os.getenv("VOICE_BITRATE_KBPS", "64")),
            "save_text": (os.getenv("VOICE_SAVE_TEXT", "1") == "1"),
        }
        voice_result = post_synthesize_and_save(voice_req)
        voice_results = voice_result.get("items", [])
        logger.info(f"Voice service synthesized {len(voice_results)} audio files.")
    else:
        logger.info("No text to synthesize, skipping Voice service.")

    # --- Finalize & Create Response ---
    logger.info("Step 5: Finalizing the plan...")
    polyline = req.polyline
    raw_legs = req.legs
    legs = _normalize_legs(raw_legs, polyline)

    assets = _normalize_assets(voice_results, llm_items)

    _write_manifest(
        pack_id,
        req.language,
        req.route,
        req.polyline,
        [s.model_dump() for s in req.segments],
        [l for l in legs],
        [w.model_dump() for w in req.waypoints_info],
        along_pois,
        assets
    )

    response = {
        "pack_id": pack_id,
        "along_pois": along_pois,
        "assets": [Asset(**a).model_dump() for a in assets],
        "manifest_url": f"/packs/{pack_id}/manifest.json",
    }

    logger.info(f"[{request_id}] Workflow finished successfully for pack_id: {pack_id}")
    return response

@app.get("/health")
def health():
    return {"status": "ok"}
