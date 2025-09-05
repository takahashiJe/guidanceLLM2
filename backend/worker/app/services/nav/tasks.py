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

# === 座標ユーティリティ ===
def _lonlat_to_coord(ll):
    # polylineの各点は [lon, lat] なので注意
    if not isinstance(ll, (list, tuple)) or len(ll) != 2:
        return None
    lon, lat = ll
    return {"lat": float(lat), "lon": float(lon)}

def _idx_to_coord(polyline, idx):
    try:
        return _lonlat_to_coord(polyline[int(idx)])
    except Exception:
        return None

# === legs 正規化（from/to 座標付与） ===
def _normalize_legs(raw_legs: list, polyline: list) -> list:
    """
    raw_legs がすでに from/to（lat/lon）を持っていたらパススルー。
    from_idx/to_idx しか無ければ polyline から取り出して付与。
    距離/時間は distance_m|distance, duration_s|duration を吸収。
    """
    out = []
    for lg in (raw_legs or []):
        mode = lg.get("mode", "car")

        # 1) 既に from/to 座標を持っている場合
        from_coord = lg.get("from") or lg.get("from_")
        to_coord   = lg.get("to")

        if isinstance(from_coord, dict) and "lat" in from_coord and "lon" in from_coord \
           and isinstance(to_coord, dict) and "lat" in to_coord and "lon" in to_coord:
            dist = lg.get("distance_m", lg.get("distance"))
            dur  = lg.get("duration_s", lg.get("duration"))
            out.append({
                "mode": mode,
                "from": {"lat": float(from_coord["lat"]), "lon": float(from_coord["lon"])},
                "to":   {"lat": float(to_coord["lat"]),   "lon": float(to_coord["lon"])},
                "distance_m": float(dist) if dist is not None else 0.0,
                "duration_s": float(dur)  if dur  is not None else 0.0,
            })
            continue

        # 2) from_idx/to_idx 型（既存実装）→ polyline から座標解決
        fidx = lg.get("from_idx")
        tidx = lg.get("to_idx")
        f = _idx_to_coord(polyline, fidx) if fidx is not None else None
        t = _idx_to_coord(polyline, tidx) if tidx is not None else None

        # 3) 万一 list で [lon,lat] が来た場合の救済
        if f is None and isinstance(from_coord, (list, tuple)) and len(from_coord) == 2:
            f = _lonlat_to_coord(from_coord)
        if t is None and isinstance(to_coord, (list, tuple)) and len(to_coord) == 2:
            t = _lonlat_to_coord(to_coord)

        dist = lg.get("distance_m", lg.get("distance"))
        dur  = lg.get("duration_s", lg.get("duration"))

        out.append({
            "mode": mode,
            "from": f or {"lat": 0.0, "lon": 0.0},
            "to":   t or {"lat": 0.0, "lon": 0.0},
            "distance_m": float(dist) if dist is not None else 0.0,
            "duration_s": float(dur)  if dur  is not None else 0.0,
        })
    return out

# === assets 正規化（audio をネスト化） ===
def _normalize_assets(voice_results: list[dict], llm_items: list[dict]) -> list[dict]:
    text_by_spot = {x.get("spot_id"): x.get("text", "") for x in (llm_items or [])}
    assets = []
    for vr in (voice_results or []):
        sid = vr.get("spot_id")
        if not sid:
            continue
        url = vr.get("url") or vr.get("audio_url")
        size = vr.get("size_bytes") or vr.get("bytes")
        dur  = vr.get("duration_sec") or vr.get("duration_s")
        fmt  = vr.get("format")
        assets.append({
            "spot_id": sid,
            "text": text_by_spot.get(sid, ""),
            "audio": {
                "url": url,
                "size_bytes": size,
                "duration_sec": dur,
                "format": fmt,
            }
        })
    return assets

# === manifest.json の書き出し（NAV 側でも残す） ===
def _write_manifest(pack_id: str, language: str, route_fc: dict,
                    polyline: list, segments: list, legs: list,
                    along_pois: list, assets: list) -> None:
    root = Path(os.getenv("PACKS_ROOT") or os.getenv("PACKS_DIR") or "/packs")
    pack_dir = (root / pack_id)
    try:
        pack_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "pack_id": pack_id,
            "language": language,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "route": route_fc,
            "polyline_len": len(polyline or []),
            "segments": segments,
            "legs": legs,
            "along_pois": along_pois,
            "assets": assets,  # audio.url など最終形を保存
        }
        p = pack_dir / "manifest.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        logger.info("NAV wrote manifest: %s", str(p))
    except Exception:
        logger.exception("NAV failed to write manifest.json for pack_id=%s", pack_id)

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
    import json
    logger.info(f"routing_result: {json.dumps(routing, indent=2, ensure_ascii=False)}")
    payload["routing_result"] = routing
    return payload

# --- ステップ2: 周辺POI検索 & LLMタスクの**シグネチャを返す** ---
@celery_app.task(name="nav.step.alongpoi_and_llm", bind=True)
def step_alongpoi_and_llm(self, payload: dict): # 戻り値の型ヒントを削除
    logger.info(f"[{self.request.id}] Step 2: AlongPOI & LLM started")
    logger.info(f"payload at start of alongpoi_and_llm: {json.dumps(payload, indent=2, ensure_ascii=False)}")
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
    # callback_task = step_merge_llm_result.s(payload=payload).set(queue="nav", immutable=True)
    
    workflow = chain(llm_task, callback_task)
    logger.info(f"payload at end of alongpoi_and_llm: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    raise self.replace(workflow)

@celery_app.task(name="nav.step.merge_llm_result", bind=True)
def step_merge_llm_result(self, llm_out: dict, payload: dict):
    """LLMの出力と元のペイロードをマージして、次の音声合成ステップに渡す。"""
    logger.info(f"[{self.request.id}] Step 2>3: merge_llm_result")
    payload["llm_items"] = llm_out.get("items", [])
    
    # 次のステップ（step_synthesize_all）を呼び出す
    # ここでは self.replace は使わず、直接次のタスクを呼び出すシグネチャを生成する
    raise self.replace(step_synthesize_all.s(payload))


# --- ステップ3: 音声合成 (LLMタスクのコールバックとして実行) ---
@celery_app.task(name="nav.step.synthesize_all", bind=True)
# def step_synthesize_all(self, llm_out: dict, *, payload: dict): # 戻り値の型ヒントを削除
def step_synthesize_all(self, llm_out: dict, payload: dict): # 戻り値の型ヒントを削除
    logger.info(f"[{self.request.id}] Step 3: Voice Synthesis Chord triggered")
    payload["llm_items"] = llm_out.get("items", [])

    if not payload["llm_items"]:
        # sig = step_finalize.s(assets_results=[], payload=payload).set(queue="nav")
        # sig = step_finalize.s([], payload).set(queue="nav")
        sig = step_finalize.s(([], payload)).set(queue="nav")
        raise self.replace(sig)

    synthesis_tasks = group(
        # ここも NAV 側で動かすので queue="nav" を明示
        step_synthesize_one.s(payload["pack_id"], payload["language"], item).set(queue="nav")
        for item in payload["llm_items"]
    )
    # callback = step_finalize.s(payload=payload).set(queue="nav")
    # callback = step_finalize.s(payload).set(queue="nav")
    callback = step_finalize_wrapper.s(payload=payload).set(queue="nav")
    
    raise self.replace(chord(synthesis_tasks, callback))

@celery_app.task(name="nav.step.finalize_wrapper")
def step_finalize_wrapper(voice_results: list[dict], *, payload: dict):
    """
    chord の結果と、チェインを通じて渡されたペイロードを
    最終化タスクへ渡すためのラッパー。
    """
    # 最終化タスクを呼び出す
    return step_finalize(voice_results, payload)

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

    audio_url  = item_res.get("audio_url")  or item_res.get("url")
    text_url   = item_res.get("text_url")
    bytes_     = item_res.get("bytes")      or item_res.get("size_bytes")
    duration_s = item_res.get("duration_s") or item_res.get("duration_sec")
    fmt        = item_res.get("format")

    return {
        "spot_id":    sid,
        "audio_url":  audio_url,
        "text_url":   text_url,
        "bytes":      bytes_,
        "duration_s": duration_s,
        "format":     fmt,
    }

# --- ステップ4: 最終化 ---
@celery_app.task(name="nav.step.finalize")
def step_finalize(voice_results: list[dict], payload: dict) -> dict:
    """
    voice の戻りを assets にネスト化しつつ、
    legs に from/to 座標を付与し、manifest.json も生成・保存する。
    """
    logger.info(f"payload in finalize: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    pack_id = payload["pack_id"]
    language = payload.get("language", "ja")

    routing = payload["routing_result"]
    route_fc = routing["feature_collection"]
    polyline = routing["polyline"]
    segments = routing["segments"]

    # legs は indices ベースのことがあるため、ここで座標付与して最終形へ
    raw_legs = routing.get("legs", [])
    logger.info(f"raw_legs: {json.dumps(raw_legs, indent=2, ensure_ascii=False)}")
    legs = _normalize_legs(raw_legs, polyline)

    along_pois = payload.get("along_pois", [])
    llm_items  = payload.get("llm_items", [])

    # assets（audio をネストへ）
    assets = _normalize_assets(voice_results, llm_items)

    # manifest.json を NAV 側でも残す（従来の仕様踏襲）
    _write_manifest(pack_id, language, route_fc, polyline, segments, legs, along_pois, assets)

    # フロント返却（ゲートウェイの PlanResponse と互換）
    resp = {
        "pack_id": pack_id,
        "route": route_fc,
        "polyline": polyline,
        "segments": segments,
        "legs": legs,
        "along_pois": along_pois,
        "assets": assets,
        # extra は許容される設定（schemas.py: extra="allow"）
        "language": language,
        "manifest_url": f"/packs/{pack_id}/manifest.json",
    }
    logger.info("[%s] Workflow finished successfully.", step_finalize.request.id)
    return resp

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