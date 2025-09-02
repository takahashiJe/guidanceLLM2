from __future__ import annotations

import os
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Literal, Optional, Dict
from hashlib import sha1
from celery import Celery, chain, group

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
    manifest_url: str  # manifest_url を追加

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
    """経路検索サービスを呼び出し、結果をペイロードに追加して返す"""
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
    return payload

# --- ステップ2: 周辺POI検索 ---
@celery_app.task(name="nav.step.alongpoi", bind=True)
def step_alongpoi(self, payload: dict) -> dict:
    """周辺POI検索サービスを呼び出し、結果をペイロードに追加して返す"""
    logger.info(f"[{self.request.id}] Step 2: AlongPOI started")
    routing_result = payload["routing_result"]
    along_req = {
        "polyline": routing_result["polyline"],
        "segments": routing_result.get("segments", []),
        "buffer": payload["buffer"]
    }
    along = post_along(along_req)
    payload["along_pois"] = along.get("pois", [])
    return payload

# --- ステップ3: LLM説明文生成 ---
@celery_app.task(name="nav.step.describe", bind=True)
def step_describe(self, payload: dict) -> dict:
    """LLMサービスを呼び出し、結果を同期的に待ってペイロードに追加する"""
    logger.info(f"[{self.request.id}] Step 3: LLM Describe started")
    waypoints = [Waypoint(**w) for w in payload["waypoints"]]
    uniq_ids = _collect_unique_spot_ids(waypoints, payload["along_pois"])
    spot_refs = _build_spot_refs(uniq_ids)

    llm_req = {"language": payload["language"], "style": "narration", "spots": spot_refs}
    for spot in spot_refs:
        if isinstance(spot.get("description"), dict):
            description_dict = spot["description"]
            spot["description"] = description_dict.get(payload["language"], description_dict.get("en", ""))
    
    logger.debug(f"NAV->LLM DEBUG: {llm_req}")
    # 別サービスのCeleryタスクを呼び出し、結果を待つ (ワーカーが別なので安全)
    async_res = _llm.send_task("llm.describe", args=[llm_req], queue="llm")
    llm_out = async_res.get(timeout=180) # タイムアウトを延長
    
    payload["llm_items"] = llm_out.get("items", [])
    return payload

# --- ステップ4: 音声合成 (並列実行の親タスク) ---
@celery_app.task(name="nav.step.synthesize_all", bind=True)
def step_synthesize_all(self, payload: dict) -> dict:
    """LLMの各テキストに対し、音声合成タスクを並列で実行し、全結果を待つ"""
    logger.info(f"[{self.request.id}] Step 4: Voice Synthesis (all) started")
    
    # 並列実行する子タスクがない場合はスキップ
    if not payload["llm_items"]:
        payload["assets"] = []
        return payload

    # 各スポットの音声合成を並列タスク(group)として定義
    synthesis_tasks = group(
        step_synthesize_one.s(payload["pack_id"], payload["language"], item)
        for item in payload["llm_items"]
    )
    
    # 全ての音声合成タスクが完了するのを待つ
    result_group = synthesis_tasks.apply_async()
    assets_results = result_group.get(timeout=180)
    
    payload["assets"] = assets_results
    return payload

# --- ステップ4a: 個別音声合成 (並列実行の子タスク) ---
@celery_app.task(name="nav.step.synthesize_one")
def step_synthesize_one(pack_id: str, language: str, item: dict) -> dict:
    """1つのスポットの音声合成を実行するタスク"""
    sid = item["spot_id"]
    logger.info(f"Executing voice synthesis for spot: {sid}")
    voice_req = {
        "language": language,
        "voice": "guide_female_1",
        "text": item["text"],
        "spot_id": sid,
        "pack_id": pack_id,
        "format": os.getenv("VOICE_FORMAT", "mp3"),
        "bitrate_kbps": int(os.getenv("VOICE_BITRATE_KBPS", "64")),
        "save_text": (os.getenv("VOICE_SAVE_TEXT", "1") == "1"),
    }
    vj = post_synthesize(voice_req)
    asset = Asset(
        spot_id=sid,
        audio_url=vj.get("audio_url"),
        text_url=vj.get("text_url"),
        bytes=vj.get("bytes"),
        duration_s=vj.get("duration_s"),
        format=vj.get("format"),
    )
    return asset.model_dump()

# --- ステップ5: 最終化 (レスポンス作成とマニフェスト保存) ---
@celery_app.task(name="nav.step.finalize", bind=True)
def step_finalize(self, payload: dict) -> dict:
    """すべての結果を統合し、最終的なPlanResponseを作成し、マニフェストを保存する"""
    logger.info(f"[{self.request.id}] Step 5: Finalize started")
    pack_id = payload["pack_id"]
    
    # 元のロジックから legs を生成
    waypoints = [Waypoint(**w) for w in payload["waypoints"]]
    spot_ids_for_coords = [w.spot_id for w in waypoints if w.spot_id]
    spot_id_to_coords = {s.spot_id: (s.lat, s.lon) for s in get_spots_by_ids(spot_ids_for_coords).values()}
    
    coords_list = [(payload["origin"]["lat"], payload["origin"]["lon"])]
    for wp in waypoints:
        if wp.spot_id in spot_id_to_coords:
            coords_list.append(spot_id_to_coords[wp.spot_id])
    # return_to_origin が True の場合などを考慮する必要があるが、元のロジックに準拠
    if len(coords_list) < len(payload["routing_result"]["legs"]) + 1:
        # 暫定的に最後の座標を追加（本来は入力にreturn_to_originを含めるべき）
        coords_list.append((payload["origin"]["lat"], payload["origin"]["lon"]))

    final_legs = []
    for leg_data in payload["routing_result"]["legs"]:
        from_coords = coords_list[leg_data["from_idx"]]
        to_coords = coords_list[leg_data["to_idx"]]
        final_legs.append({
            "mode": leg_data["mode"],
            "from": {"lat": from_coords[0], "lon": from_coords[1]},
            "to": {"lat": to_coords[0], "lon": to_coords[1]},
            "distance_m": leg_data["distance"],
            "duration_s": leg_data["duration"]
        })

    # manifest を生成
    polyline = payload["routing_result"]["polyline"]
    segments = payload["routing_result"].get("segments", [])
    manifest = {
        "pack_id": pack_id,
        "language": payload["language"],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "route_digest": sha1(json.dumps(polyline, separators=(',',':')).encode()).hexdigest(),
        "segments": segments,
        "assets": payload["assets"]
    }
    manifest_path = Path(os.environ.get("PACKS_DIR","/packs")) / pack_id / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    manifest_url = f"{os.environ.get('PACKS_BASE_URL','/packs')}/{pack_id}/manifest.json"

    # APIレスポンスを構築
    response = PlanResponse(
        pack_id=pack_id,
        route=payload["routing_result"]["feature_collection"],
        legs=final_legs,
        along_pois=payload["along_pois"],
        assets=[Asset(**a) for a in payload["assets"]],
        manifest_url=manifest_url,
    )
    logger.info(f"[{self.request.id}] Workflow finished successfully.")
    return response.model_dump(by_alias=True)


# =================================================================
# ==== Workflow Entrypoint Task (APIから呼び出されるタスク) ====
# =================================================================
@celery_app.task(name="nav.plan", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def plan_workflow_entrypoint(self, payload: Dict[str, Any]):
    """
    リクエストを受け取り、一連の処理をチェインとして定義・実行する。
    このタスク自体はすぐに終了し、ワークフロー全体のAsyncResultを返す。
    """
    # 各タスクで共有するユニークなIDを生成
    pack_id = str(uuid.uuid4())
    payload["pack_id"] = pack_id
    
    # タスクのチェインを定義
    workflow = chain(
        step_routing.s(payload),
        step_alongpoi.s(),
        step_describe.s(),
        step_synthesize_all.s(),
        step_finalize.s()
    )
    
    # ワークフローを非同期で実行開始
    # replace()を使うことで、このタスクIDがワークフロー全体の状態を追跡するようになる
    raise self.replace(workflow)