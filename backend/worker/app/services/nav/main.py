from __future__ import annotations

import os
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Literal, Optional, Dict
from hashlib import sha1
from celery import Celery

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.worker.app.services.nav.celery_app import celery_app
from backend.worker.app.services.nav.client_routing import post_route
from backend.worker.app.services.nav.client_alongpoi import post_along
from backend.worker.app.services.nav.client_llm import post_describe
from backend.worker.app.services.nav.client_voice import post_synthesize
from backend.worker.app.services.nav.spot_repo import get_spots_by_ids

import logging # ファイルの先頭に追加
logger = logging.getLogger(__name__)

_llm = Celery(
    "nav-llm-producer",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)

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
    # Pydanticのキーワード衝突回避のため alias を使用
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
    legs: List[Leg]  # ここが修正後のLegを参照するようにする
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

def _call_llm_describe(llm_payload: Dict[str, Any], timeout_sec: int = 60) -> Dict[str, Any]:
    """
    既存の `HTTP POST /describe` 呼び出し部分を置き換える関数。
    入出力スキーマは従来の /describe と同一（llm/main.py の Celery タスクに対応）。
    """
    async_res = celery_app.send_task("llm.describe", args=[llm_payload], queue="llm")
    result = async_res.get()
    return result

def plan_impl(payload: Dict[str, Any]) -> Dict[str, Any]:
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
    route_fc = routing["feature_collection"]
    legs_from_routing = routing["legs"]
    polyline = routing["polyline"]
    segments = routing.get("segments", [])
    spot_id_to_coords = {s.spot_id: (s.lat, s.lon) for s in get_spots_by_ids([w.spot_id for w in payload.waypoints]).values()}
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
    for spot in spot_refs:
        # description が辞書形式であることを確認
        if isinstance(spot.get("description"), dict):
            # payload.language (e.g., "ja") をキーにして文字列を抽出する。
            # もし指定された言語の翻訳が存在しない場合は、英語("en")にフォールバックし、
            # それもなければ空文字を設定してエラーを防ぐ。
            description_dict = spot["description"]
            spot["description"] = description_dict.get(payload.language, description_dict.get("en", ""))
    print(f"NAV→LLM DEBUG: {llm_req}")
    llm_out = _call_llm_describe(llm_req, timeout_sec=60)  # {"items":[{"spot_id","text"}]}

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

@celery_app.task(
    name="nav.plan",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def plan_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    入力・出力スキーマは既存の /plan と完全に同じ。
    処理内容も plan_impl() にそのまま残してあり、ここから呼ぶだけ。
    """
    logger.info("nav.plan started")
    out = plan_impl(payload)
    logger.info("nav.plan done")
    return out