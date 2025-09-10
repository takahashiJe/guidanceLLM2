# backend/api/realtime_router.py
from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, Optional
from typing_extensions import TypedDict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None  # type: ignore

router = APIRouter(prefix="/rt", tags=["realtime"])

# ==============================
# 返却ペイロード（極小JSON）
# ==============================
# w (now): 0=sun,1=cloud,2=rain
# u (upcoming): 0=none,1=to_cloud,2=to_rain,3=to_sun
# h: hours ahead (u>0 のときのみ出現)
# c: congestion 0..4
class RTDoc(TypedDict, total=False):
    s: str
    w: int
    u: int
    h: Optional[int]
    c: int

# メモリ上に最新値のみ保持（spot_id -> RTDoc）
_state: Dict[str, RTDoc] = {}

# ==============================
# MQTT クライアント（このファイル内で完結）
# ==============================
_MQTT_THREAD: Optional[threading.Thread] = None
_MQTT_CLIENT: Optional["mqtt.Client"] = None
_MQTT_STOP = threading.Event()

# 期待するトピック（例）： rt/spot/<spot_id>
# ペイロード例:
#   {"w":0,"u":2,"h":2,"c":3} / {"w":1,"u":0,"c":1} / {"w":2,"u":3,"h":4,"c":2}
MQTT_BROKER = os.getenv("RT_MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("RT_MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("RT_MQTT_USER") or None
MQTT_PASSWORD = os.getenv("RT_MQTT_PASS") or None
MQTT_TOPIC = os.getenv("RT_MQTT_TOPIC", "rt/spot/#")  # ワイルドカード購読

def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(MQTT_TOPIC, qos=1)

def _on_message(client, userdata, msg):
    # トピック例: rt/spot/spot_hottai_falls
    parts = msg.topic.split("/")
    spot_id = parts[-1] if parts else None
    if not spot_id:
        return
    try:
        doc = json.loads(msg.payload.decode("utf-8"))
        # 期待形式：{"w":0..2, "u":0..3, "h":<int 任意>, "c":0..4}
        w = int(doc.get("w"))
        u = int(doc.get("u"))
        c = int(doc.get("c"))
        item: RTDoc = {"s": spot_id, "w": w, "u": u, "c": c}
        # u>0 のときのみ h を保持（省バイトのため）
        if u > 0 and "h" in doc and doc["h"] is not None:
            item["h"] = int(doc["h"])
        _state[spot_id] = item
    except Exception:
        # 壊れたメッセージは無視（必要ならログに出す）
        return

def _mqtt_worker():
    global _MQTT_CLIENT
    if mqtt is None:
        return
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = _on_connect
    client.on_message = _on_message
    _MQTT_CLIENT = client
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    client.loop_start()
    try:
        while not _MQTT_STOP.is_set():
            time.sleep(0.2)
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

@router.on_event("startup")
def _startup_mqtt():
    if mqtt is None:
        return
    global _MQTT_THREAD
    if _MQTT_THREAD and _MQTT_THREAD.is_alive():
        return
    _MQTT_STOP.clear()
    _MQTT_THREAD = threading.Thread(target=_mqtt_worker, name="rt-mqtt", daemon=True)
    _MQTT_THREAD.start()

@router.on_event("shutdown")
def _shutdown_mqtt():
    if mqtt is None:
        return
    _MQTT_STOP.set()

# ==============================
# HTTP エンドポイント
# ==============================
@router.get("/spot/{spot_id}", response_class=JSONResponse, summary="最新のリアルタイム情報（極小JSON）")
def get_spot_rt(spot_id: str):
    """
    返却例:
      {"s":"spotA","w":0,"u":0,"c":1}
      {"s":"spotB","w":0,"u":2,"h":2,"c":3}
      {"s":"spotC","w":1,"u":3,"h":3,"c":0}
    """
    item = _state.get(spot_id)
    if not item:
        # データ未到達時は 204 No Content（フロントはリトライ）
        return JSONResponse(status_code=204, content=None)
    # 余計なキーを持たないように，u==0 のとき h を除去して返す（保守的）
    if item.get("u", 0) == 0 and "h" in item:
        item = {k: v for k, v in item.items() if k != "h"}
    return JSONResponse(content=item)

# ---（開発用）モック注入エンドポイント（本番では外すか認証で保護） ---
@router.post("/_mock/{spot_id}")
def _mock_push(spot_id: str, body: RTDoc):
    """
    開発用にHTTPから直接最新値を書き込む（LoRa/MQTTなしで疎通確認可能）
    例:
      {"w":0,"u":2,"h":2,"c":1}
      {"w":1,"u":0,"c":3}
      {"w":2,"u":3,"h":4,"c":2}
    """
    body["s"] = spot_id
    # u==0 のときは h を持たせない
    if body.get("u", 0) == 0 and "h" in body:
        body.pop("h", None)
    _state[spot_id] = body
    return {"ok": True}
