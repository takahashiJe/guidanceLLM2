from __future__ import annotations

import os
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Literal, Optional, Dict
from hashlib import sha1
from celery import Celery, chain, group, chord

from pydantic import BaseModel, Field

from backend.worker.app.services.nav.celery_app import celery_app
from backend.worker.app.services.nav.client_routing import post_route
from backend.worker.app.services.nav.client_alongpoi import post_along
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

def _build_spot_refs(spot_ids: List[str]) -> List[dict]:
    spot_rows = get_spots_by_ids(spot_ids).values()
    items = [
        {
            "spot_id": row.spot_id,
            "name": row.name,
            "description": row.description,
            "md_slug": row.md_slug,
        }
        for row in spot_rows
    ]
    return items

# =================================================================
# ==== Celery Workflow Tasks (ワークフローを構成するタスク群) ====
# =================================================================

# --- ステップ1: 経路検索 ---
@celery_app.task(name="nav.step.routing", bind=True)
def step_routing(self, payload: dict) -> dict:
    logger.info(f"[{self.request.id}] Step 1: Routing started")
    req = PlanRequest(**payload)
    payload.update(req.model_dump())

    routing_req = {
        "origin": req.origin.model_dump(),
        "waypoints": [w.model_dump() for w in req.waypoints],
        "car_to_trailhead": True
    }
    routing = post_route(routing_req)
    payload["routing_result"] = routing
    return payload

# --- ステップ2: 周辺POI検索 & LLMタスクの**シグネチャを返す** ---
@celery_app.task(name="nav.step.alongpoi_and_llm", bind=True)
def step_alongpoi_and_llm(self, payload: dict): # 戻り値の型ヒントを削除
    logger.info(f"[{self.request.id}] Step 2: AlongPOI & LLM started")
    routing_result = payload["routing_result"]
    along_req = {
        "polyline": routing_result["polyline"],
        "segments": routing_result.get("segments", []),
        "buffer": payload["buffer"]
    }
    along = post_along(along_req)
    payload["along_pois"] = along.get("pois", [])

    waypoints = [Waypoint(**w) for w in payload["waypoints"]]
    uniq_ids = _collect_unique_spot_ids(waypoints, payload["along_pois"])
    spot_refs = _build_spot_refs(uniq_ids)

    llm_req = {"language": payload["language"], "style": "narration", "spots": spot_refs}
    for spot in spot_refs:
        if isinstance(spot.get("description"), dict):
            description_dict = spot["description"]
            spot["description"] = description_dict.get(payload["language"], description_dict.get("en", ""))

    logger.debug(f"NAV->LLM DEBUG: {llm_req}")

    # 【修正点】
    # 次のステップ（step_synthesize_all）にペイロードを渡すタスクのシグネチャを作成し、
    # それをLLMタスクのコールバックとして設定したチェインを返す。
    llm_task = celery_app.signature("llm.describe", args=[llm_req], queue="llm")
    callback_task = step_synthesize_all.s(payload=payload).set(queue="nav")
    
    workflow = chain(llm_task, callback_task)
    raise self.replace(workflow)


# --- ステップ3: 音声合成 (LLMタスクのコールバックとして実行) ---
@celery_app.task(name="nav.step.synthesize_all", bind=True)
def step_synthesize_all(self, llm_out: dict, *, payload: dict): # 戻り値の型ヒントを削除
    logger.info(f"[{self.request.id}] Step 3: Voice Synthesis Chord triggered")
    payload["llm_items"] = llm_out.get("items", [])

    if not payload["llm_items"]:
        sig = step_finalize.s(assets_results=[], payload=payload).set(queue="nav")
        raise self.replace(sig)

    synthesis_tasks = group(
        # ここも NAV 側で動かすので queue="nav" を明示
        step_synthesize_one.s(payload["pack_id"], payload["language"], item).set(queue="nav")
        for item in payload["llm_items"]
    )
    callback = step_finalize.s(payload=payload).set(queue="nav")
    
    raise self.replace(chord(synthesis_tasks, callback))


# --- ステップ3a: 個別音声合成 ---
@celery_app.task(name="nav.step.synthesize_one")
def step_synthesize_one(pack_id: str, language: str, item: dict) -> dict:
    sid = item["spot_id"]
    logger.info(f"Executing voice synthesis for spot: {sid}")
    # 【重要】/synthesize_and_save を呼び出すように修正
    voice_req = {
        "pack_id": pack_id,
        "language": language,
        "items": [{"spot_id": sid, "text": item["text"]}],
        "preferred_format": os.getenv("VOICE_FORMAT", "mp3"),
        "bitrate_kbps": int(os.getenv("VOICE_BITRATE_KBPS", "64")),
        "save_text": (os.getenv("VOICE_SAVE_TEXT", "1") == "1"),
    }
    # post_synthesize から post_synthesize_and_save に変更
    vj = post_synthesize_and_save(voice_req)
    # 戻り値の構造が違うので合わせる
    item_res = vj["items"][0] if vj.get("items") else {}

    return {
        "spot_id": sid,
        "audio_url": item_res.get("url"),
        "text_url": item_res.get("text_url"),
        "bytes": item_res.get("size_bytes"),
        "duration_s": item_res.get("duration_sec"),
        "format": item_res.get("format"),
    }

# --- ステップ4: 最終化 ---
@celery_app.task(name="nav.step.finalize", bind=True)
def step_finalize(self, assets_results: list, payload: dict) -> dict:
    # このタスクの中身は変更なしでOK
    logger.info(f"[{self.request.id}] Step 4: Finalize started")
    llm_items_map = {item['spot_id']: item for item in payload.get("llm_items", [])}
    
    final_assets = []
    for asset_result in assets_results:
        spot_id = asset_result["spot_id"]
        text_content = llm_items_map.get(spot_id, {}).get("text", "")
        
        audio_data = None
        if asset_result.get("audio_url"):
            audio_data = {
                "url": asset_result["audio_url"],
                "size_bytes": asset_result["bytes"],
                "duration_sec": asset_result["duration_s"],
                "format": asset_result["format"],
            }

        final_assets.append({
            "spot_id": spot_id,
            "text": text_content,
            "audio": audio_data,
        })
    payload["assets"] = final_assets
    pack_id = payload["pack_id"]
    
    waypoints = [Waypoint(**w) for w in payload.get("waypoints", [])]
    spot_ids_for_coords = [w.spot_id for w in waypoints if w.spot_id]
    spot_id_to_coords = {s.spot_id: (s.lat, s.lon) for s in get_spots_by_ids(spot_ids_for_coords).values()}
    
    coords_list = [(payload["origin"]["lat"], payload["origin"]["lon"])]
    for wp in waypoints:
        if wp.spot_id in spot_id_to_coords:
            coords_list.append(spot_id_to_coords[wp.spot_id])
    if payload.get('return_to_origin', True):
        coords_list.append((payload["origin"]["lat"], payload["origin"]["lon"]))

    final_legs = []
    for leg_data in payload["routing_result"]["legs"]:
        from_idx, to_idx = leg_data.get("from_idx", 0), leg_data.get("to_idx", 1)
        if from_idx < len(coords_list) and to_idx < len(coords_list):
            from_coords, to_coords = coords_list[from_idx], coords_list[to_idx]
            final_legs.append({
                "mode": leg_data["mode"], "from": {"lat": from_coords[0], "lon": from_coords[1]},
                "to": {"lat": to_coords[0], "lon": to_coords[1]},
                "distance_m": leg_data["distance"], "duration_s": leg_data["duration"]
            })

    polyline = payload["routing_result"]["polyline"]
    segments = payload["routing_result"].get("segments", [])
    manifest = {
        "pack_id": pack_id, "language": payload["language"],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "route_digest": sha1(json.dumps(polyline, separators=(',',':')).encode()).hexdigest(),
        "segments": segments, "assets": payload["assets"]
    }
    manifest_path = Path(os.environ.get("PACKS_DIR","/packs")) / pack_id / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    response_data = {
        "pack_id": pack_id,
        "route": payload["routing_result"]["feature_collection"],
        "polyline": polyline,
        "segments": segments,
        "legs": final_legs,
        "along_pois": payload["along_pois"],
        "assets": payload["assets"],
    }
    
    logger.info(f"[{self.request.id}] Workflow finished successfully.")
    return response_data

# =================================================================
# ==== Workflow Entrypoint Task (APIから呼び出されるタスク) ====
# =================================================================
@celery_app.task(name="nav.plan", bind=True)
def plan_workflow_entrypoint(self, payload: Dict[str, Any]):
    pack_id = str(uuid.uuid4())
    payload["pack_id"] = pack_id
    
    workflow = chain(
        step_routing.s(payload).set(queue="nav"),
        step_alongpoi_and_llm.s().set(queue="nav"),
    )
    
    # self.replace で現在のタスクをこのワークフローに置き換える
    raise self.replace(workflow)