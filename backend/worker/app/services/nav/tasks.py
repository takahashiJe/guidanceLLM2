# backend/worker/app/services/nav/tasks.py

from __future__ import annotations

import os
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Literal, Optional, Dict, Any, Tuple

from pydantic import BaseModel, Field
from celery import Celery

from shapely.geometry import Point, LineString
from shapely.ops import transform
from pyproj import Transformer

from backend.worker.app.services.nav.celery_app import celery_app

# 各サービスを呼び出すためのHTTPクライアント
from backend.worker.app.services.nav.client_routing import post_route
from backend.worker.app.services.nav.client_alongpoi import post_along
from backend.worker.app.services.nav.client_llm import post_describe
from backend.worker.app.services.nav.client_voice import post_synthesize_and_save

from backend.worker.app.services.nav.spot_repo import get_spots_by_ids

import logging
logger = logging.getLogger(__name__)

# =================================================================
# ==== Schemas (スキーマ定義) ====
# =================================================================
class Waypoint(BaseModel):
    spot_id: Optional[str] = None

class Coord(BaseModel):
    lat: float
    lon: float

class PlanRequest(BaseModel):
    language: Literal["ja", "en", "zh"]
    origin: Coord
    waypoints: List[Waypoint]
    return_to_origin: bool = True
    buffer: dict = Field(default_factory=lambda: {"car": 300, "foot": 10})

class Leg(BaseModel):
    mode: Literal["car", "foot"]
    from_: Coord = Field(..., alias="from")
    to: Coord
    distance_m: float
    duration_s: float

class Asset(BaseModel):
    spot_id: str
    narration_type: Optional[str] = None # ★★★ フロントエンド識別のために追加 ★★★
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
    manifest_url: str

# ★★★ 状況説明の定義 ★★★
CONDITIONAL_NARRATIONS = {
    "weather_1": "w=1 (Cloudy)",
    "weather_2": "w=2 (Rainy)",
    "congestion_1": "c=1 (Congested)",
    "congestion_2": "c=2 (Full)",
}

# =================================================================
# ==== Helpers (ヘルパー関数) ====
# =================================================================
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

def _lonlat_to_coord(ll):
    if not isinstance(ll, (list, tuple)) or len(ll) != 2: return None
    lon, lat = ll
    return {"lat": float(lat), "lon": float(lon)}

def _idx_to_coord(polyline, idx):
    try:
        return _lonlat_to_coord(polyline[int(idx)])
    except Exception:
        return None

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
    """
    LLMとVoiceの結果をマージし、フロントエンド向けのAssetリストを作成する。
    spot_id と narration_type を使って、正しくメタデータを付与する。
    """
    # LLMへのリクエストアイテムを (spot_id, narration_type) のタプルをキーとする辞書に格納
    llm_item_map = {
        (item.get("spot_id"), item.get("narration_type")): item
        for item in llm_items
    }

    assets = []
    processed_keys = set()

    # 音声生成が成功したアイテムを処理
    for vr in voice_results or []:
        sid = vr.get("spot_id")
        ntype = vr.get("narration_type")  # Voiceサービスがこのキーをパススルーすることを期待
        if not sid:
            continue

        key = (sid, ntype)
        if key in llm_item_map:
            llm_item = llm_item_map[key]
            assets.append({
                "spot_id": sid,
                "narration_type": ntype,
                "text": llm_item.get("text", ""),
                "audio_url": vr.get("audio_url"),
                "text_url": vr.get("text_url"),
                "bytes": vr.get("bytes"),
                "duration_s": vr.get("duration_s"),
                "format": vr.get("format"),
            })
            processed_keys.add(key)

    # 音声生成に失敗したか、そもそも音声生成がなかったアイテムを処理 (テキスト情報のみ)
    for key, item in llm_item_map.items():
        if key not in processed_keys:
            assets.append({
                "spot_id": item.get("spot_id"),
                "narration_type": item.get("narration_type"),
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

def _proj() -> Transformer:
    return Transformer.from_crs(4326, 3857, always_xy=True)

def _reduce_hits_to_along_pois_local(hits: List[Dict], polyline: List[List[float]]) -> List[Dict]:
    if not hits or not polyline or len(polyline) < 2:
        return []

    to3857 = _proj().transform
    line_lonlat = [(p[0], p[1]) for p in polyline]
    line_3857 = transform(to3857, LineString(line_lonlat))
    segs_3857 = []
    for i in range(len(line_lonlat) - 1):
        seg = LineString([line_lonlat[i], line_lonlat[i + 1]])
        segs_3857.append(transform(to3857, seg))

    out: List[Dict] = []
    for h in hits:
        lon, lat = float(h["lon"]), float(h["lat"])
        pt_3857 = transform(to3857, Point(lon, lat))
        dist_m = float(line_3857.distance(pt_3857))
        best_idx = 0
        best_d = float("inf")
        for i, seg in enumerate(segs_3857):
            d = seg.distance(pt_3857)
            if d < best_d:
                best_d = d
                best_idx = i

        distance_m = float(h.get("distance_m", dist_m))
        out.append(
            {
                "spot_id": h.get("spot_id"),
                "name": h.get("name"),
                "lon": float(h.get("lon")) if "lon" in h else None,
                "lat": float(h.get("lat")) if "lat" in h else None,
                "kind": h.get("kind"),
                "nearest_idx": int(best_idx),
                "distance_m": distance_m,
                "source_segment_mode": h.get("source_segment_mode"),
            }
        )
    return out

# =================================================================
# ==== Main Workflow Task ====
# =================================================================
@celery_app.task(name="nav.plan", bind=True)
def plan_workflow(self, payload: Dict[str, Any]) -> dict:
    pack_id = str(uuid.uuid4())
    payload["pack_id"] = pack_id
    req = PlanRequest(**payload)
    logger.info(f"[{self.request.id}] Workflow started for pack_id: {pack_id}")

    # --- 1. Routing Service ---
    logger.info("Step 1: Calling Routing service...")
    routing_req = {"origin": req.origin.model_dump(), "waypoints": [w.model_dump() for w in req.waypoints], "car_to_trailhead": True}
    routing_result = post_route(routing_req)
    logger.info("Routing service returned.")

    # --- 2. AlongPOI Service ---
    logger.info("Step 2: Calling AlongPOI service...")
    waypoint_ids = [w.spot_id for w in req.waypoints if w.spot_id and w.spot_id != "current"]
    along_req = {"polyline": routing_result["polyline"], "segments": routing_result.get("segments", []), "buffer": req.buffer, "waypoints": waypoint_ids}
    along_result = post_along(along_req)
    along_pois = along_result.get("pois", [])
    logger.info(f"AlongPOI service returned {len(along_pois)} POIs.")

    # --- 3. LLM Service ---
    logger.info("Step 3: Calling LLM service...")
    # (A) 全てのスポット(Waypoint + AlongPOI)の通常案内をリクエスト
    all_spot_ids = _collect_unique_spot_ids(req.waypoints, along_pois)
    spot_refs = _build_spot_refs(all_spot_ids, req.language)

    # (B) Waypointに限定して、状況説明(4パターン)をリクエスト
    conditional_spot_refs = []
    waypoint_spot_refs = [ref for ref in spot_refs if ref['spot_id'] in waypoint_ids]

    for spot_ref in waypoint_spot_refs:
        for key in CONDITIONAL_NARRATIONS.keys():
            conditional_ref = spot_ref.copy()
            conditional_ref["situation_type"] = key
            conditional_spot_refs.append(conditional_ref)

    # (C) スポットガイダンスと状況説明を結合してLLMに一括送信
    combined_spots_for_llm = spot_refs + conditional_spot_refs

    llm_items = []
    if combined_spots_for_llm:
        llm_req = {"language": req.language, "style": "situation", "spots": combined_spots_for_llm}
        llm_result = post_describe(llm_req)
        llm_items = llm_result.get("items", [])
        logger.info(f"LLM service returned {len(llm_items)} descriptions.")
    else:
        logger.info("No spots to describe, skipping LLM service.")

    # --- 4. Voice Service ---
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

    # --- 5. Finalize & Create Response ---
    logger.info("Step 5: Finalizing the plan...")
    polyline = routing_result["polyline"]
    raw_legs = routing_result.get("legs", [])
    legs = _normalize_legs(raw_legs, polyline)

    assets = _normalize_assets(voice_results, llm_items)

    waypoint_id_set = set(waypoint_ids)
    waypoint_spot_data = [s for s in spot_refs if s['spot_id'] in waypoint_id_set]
    waypoints_info = _reduce_hits_to_along_pois_local(waypoint_spot_data, polyline)

    _write_manifest(
        pack_id, req.language, routing_result["feature_collection"],
        polyline, routing_result["segments"], legs,
        waypoints_info,
        along_pois,
        assets
    )

    response = {
        "pack_id": pack_id,
        "route": routing_result["feature_collection"],
        "polyline": polyline,
        "segments": routing_result["segments"],
        "legs": legs,
        "waypoints_info": waypoints_info,
        "along_pois": along_pois,
        "assets": [Asset(**a).model_dump() for a in assets], # スキーマで検証
        "language": req.language,
        "manifest_url": f"/packs/{pack_id}/manifest.json",
    }

    logger.info(f"[{self.request.id}] Workflow finished successfully for pack_id: {pack_id}")
    return response