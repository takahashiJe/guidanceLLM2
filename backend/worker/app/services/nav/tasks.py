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
from backend.worker.app.services.nav.client_voice import post_synthesize
from backend.worker.app.services.nav.spot_repo import get_spots_by_ids

import logging
logger = logging.getLogger(__name__)

# LLMサービスを呼び出すためのCeleryインスタンス
_llm = Celery(
    "nav-llm-producer",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)

_llm.conf.update(
    task_serializer="json",
    accept_content=["json"],
)

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
    payload = req.model_dump(by_alias=True)

    routing_req = {
        "origin": req.origin.model_dump(),
        "waypoints": [w.model_dump() for w in req.waypoints],
        "car_to_trailhead": True
    }
    routing = post_route(routing_req)
    payload["routing_result"] = routing
    print(f"【pack_id DEBUG】ステップ1：payload[pack_id]={payload['pack_id']}")
    return payload

# --- ステップ2: 周辺POI検索 & LLMタスクの発行 ---
@celery_app.task(name="nav.step.alongpoi_and_trigger_llm", bind=True)
def step_alongpoi_and_trigger_llm(self, payload: dict) -> None:
    logger.info(f"[{self.request.id}] Step 2: AlongPOI & Trigger LLM started")
    # AlongPOIの処理
    routing_result = payload["routing_result"]
    along_req = {
        "polyline": routing_result["polyline"],
        "segments": routing_result.get("segments", []),
        "buffer": payload["buffer"]
    }
    along = post_along(along_req)
    payload["along_pois"] = along.get("pois", [])

    # LLMタスクの準備
    waypoints = [Waypoint(**w) for w in payload["waypoints"]]
    uniq_ids = _collect_unique_spot_ids(waypoints, payload["along_pois"])
    spot_refs = _build_spot_refs(uniq_ids)

    llm_req = {"language": payload["language"], "style": "narration", "spots": spot_refs}
    for spot in spot_refs:
        if isinstance(spot.get("description"), dict):
            description_dict = spot["description"]
            spot["description"] = description_dict.get(payload["language"], description_dict.get("en", ""))
    
    logger.debug(f"NAV->LLM DEBUG: {llm_req}")

    # step_synthesize_allがchord経由でfinalizeを呼ぶので、ここでのchainは不要
    callback_task = step_synthesize_all.s(payload=payload).set(queue="nav")
    # LLMタスクを投入し、完了後の処理として上記チェインを `link` で予約
    _llm.send_task("llm.describe", args=[llm_req], queue="llm", link=callback_task)
    
    # このタスクの役目はここまで。後続処理はlinkに任せる。
    return

# --- ステップ3: 音声合成 (LLMタスクのコールバックとして実行) ---
@celery_app.task(name="nav.step.synthesize_all", bind=True)
def step_synthesize_all(self, llm_out: dict, *, payload: dict) -> None:
    logger.info(f"[{self.request.id}] Step 3: Voice Synthesis Chord triggered")
    payload["llm_items"] = llm_out.get("items", [])

    # llm_itemsが空なら、すぐにfinalizeを呼んで終了
    if not payload["llm_items"]:
        # step_finalizeは結果リストを第一引数に取るので空リストを渡す
        step_finalize.delay(assets_results=[], payload=payload)
        return

    # Chordのヘッダー：並列実行される個別の音声合成タスクのグループ
    synthesis_tasks = group(
        step_synthesize_one.s(payload["pack_id"], payload["language"], item)
        for item in payload["llm_items"]
    )
    
    # Chordのコールバック（ボディ）：ヘッダーのタスク結果が第一引数に渡される
    # payloadは第二引数として渡すように.s()で部分適用しておく
    callback_task = step_finalize.s(payload=payload).set(queue="nav")

    # Chordを定義して実行
    chord(synthesis_tasks)(callback_task)

    # このタスクの役目はChordを起動することなので、戻り値はなし
    return

# --- ステップ3a: 個別音声合成 ---
@celery_app.task(name="nav.step.synthesize_one")
def step_synthesize_one(pack_id: str, language: str, item: dict) -> dict:
    sid = item["spot_id"]
    logger.info(f"Executing voice synthesis for spot: {sid}")
    voice_req = {
        "language": language, "voice": "guide_female_1", "text": item["text"],
        "spot_id": sid, "pack_id": pack_id,
        "format": os.getenv("VOICE_FORMAT", "mp3"),
        "bitrate_kbps": int(os.getenv("VOICE_BITRATE_KBPS", "64")),
        "save_text": (os.getenv("VOICE_SAVE_TEXT", "1") == "1"),
    }
    vj = post_synthesize(voice_req)
    asset = Asset(
        spot_id=sid, audio_url=vj.get("audio_url"), text_url=vj.get("text_url"),
        bytes=vj.get("bytes"), duration_s=vj.get("duration_s"), format=vj.get("format"),
    )
    return asset.model_dump()

# --- ステップ4: 最終化 ---
@celery_app.task(name="nav.step.finalize", bind=True)
def step_finalize(self, assets_results: list, payload: dict) -> dict:
    logger.info(f"[{self.request.id}] Step 4: Finalize started")
    payload["assets"] = assets_results
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
    manifest_url = f"{os.environ.get('PACKS_BASE_URL','/packs')}/{pack_id}/manifest.json"

    response = PlanResponse(
        pack_id=pack_id, route=payload["routing_result"]["feature_collection"],
        legs=final_legs, along_pois=payload["along_pois"],
        assets=[Asset(**a) for a in payload["assets"]], manifest_url=manifest_url,
    )
    logger.info(f"[{self.request.id}] Workflow finished successfully.")
    return response.model_dump(by_alias=True)

# =================================================================
# ==== Workflow Entrypoint Task (APIから呼び出されるタスク) ====
# =================================================================
@celery_app.task(name="nav.plan", bind=True)
def plan_workflow_entrypoint(self, payload: Dict[str, Any]):
    pack_id = str(uuid.uuid4())
    payload["pack_id"] = pack_id
    print(f"【pack_id DEBUG】ステップ0：payload[pack_id]={payload['pack_id']}")
    
    # ワークフローを短縮化。残りはlinkによるコールバックが処理する。
    workflow = chain(
        step_routing.s(payload),
        step_alongpoi_and_trigger_llm.s(),
    )
    
    raise self.replace(workflow)