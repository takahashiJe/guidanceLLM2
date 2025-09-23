from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, Optional
from typing_extensions import TypedDict
import base64  # ★★★ Base64デコードのためにインポート

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.responses import Response

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("デバッグログ")

router = APIRouter(prefix="/rt", tags=["realtime"])

class RTDoc(TypedDict, total=False):
    s: str
    w: int
    c: int

_state: Dict[str, RTDoc] = {}
_MQTT_CLIENT: Optional["mqtt.Client"] = None
_MQTT_STOP = threading.Event()

# ==============================
# ★★★ TTN MQTT設定 ★★★
# 環境変数からTTNの情報を取得
# ==============================
MQTT_BROKER = os.getenv("RT_MQTT_BROKER", "au1.cloud.thethings.network")
MQTT_PORT = int(os.getenv("RT_MQTT_PORT", "8883"))
MQTT_USERNAME = os.getenv("RT_MQTT_USER") # TTNのApplication ID + "@ttn"
MQTT_PASSWORD = os.getenv("RT_MQTT_PASS") # TTNで生成したAPIキー

# ★★★ TTNのApplication IDとDevice IDを環境変数から取得 ★★★
TTN_APP_ID = os.getenv("TTN_APP_ID")
TTN_DEVICE_ID = os.getenv("TTN_DEVICE_ID")

# ★★★ TTNの正しいUplink/Downlinkトピックを定義 ★★★
MQTT_UPLINK_TOPIC = f"v3/{TTN_APP_ID}@ttn/devices/{TTN_DEVICE_ID}/up"
# MQTT_UPLINK_TOPIC = f"v3/{TTN_APP_ID}/devices/+/up"
MQTT_DOWNLINK_TOPIC = f"v3/{TTN_APP_ID}/devices/{TTN_DEVICE_ID}/down/push"

def _status_monitor():
    while True:
        if _MQTT_CLIENT:
            print(f"【DEBUG】MQTTクライアント接続状態: {_MQTT_CLIENT.is_connected()}")
        else:
            print("【DEBUG】MQTTクライアント未初期化")
        time.sleep(60)

def _on_connect(client, userdata, flags, rc, properties=None):
    print(f"【DEBUG】_on_connect呼ばれました。 rc={rc}")
    if rc == 0:
        print(f"【DEBUG】MQTTブローカーに接続成功。トピックを購読します: {MQTT_UPLINK_TOPIC}")
        result, mid = client.subscribe(MQTT_UPLINK_TOPIC, qos=1)
        print(f"【DEBUG】subscribe呼び出し結果: {result}, mid: {mid}")
    else:
        print(f"【ERROR】MQTTブローカーへ接続失敗。コード: {rc}")

def _on_message(client, userdata, msg):
    """ ★★★ TTNからのUplinkメッセージを処理する関数 ★★★ """
    print(f"【DEBUG】MQTTメッセージ受信コールバック開始")
    print(f"【DEBUG】トピック={msg.topic}")
    print(f"【DEBUG】ペイロード長={len(msg.payload)}")
    print(f"【DEBUG】ペイロード（バイト列）: {list(msg.payload)}")
    try:
        decoded_payload = msg.payload.decode("utf-8")
        print(f"【DEBUG】ペイロードデコード済み: {decoded_payload}")
        ttn_msg = json.loads(msg.payload.decode("utf-8"))
        print(f"TTNメッセージ内容: {json.dumps(ttn_msg, indent=2, ensure_ascii=False)}")

        # 'data' キーが存在し、その中に 'uplink_message' があるかチェック
        if "data" in ttn_msg and "uplink_message" in ttn_msg["data"]:
            uplink = ttn_msg["data"]["uplink_message"]
        # 'data' キーがないトップレベルのuplink_messageも念のためチェック
        elif "uplink_message" in ttn_msg:
            uplink = ttn_msg["uplink_message"]
        else:
            return # 該当するメッセージでなければ終了

        if "frm_payload" not in uplink:
            return

        # Base64エンコードされたペイロードを取得
        payload_b64 = uplink["frm_payload"]

        # payload_b64 = ttn_msg["uplink_message"]["frm_payload"]
        # Base64デコードして元のspot_idを取得
        spot_id = base64.b64decode(payload_b64).decode("utf-8")
        print(f"TTNからUplink受信: spot_id = {spot_id}")

        # --- ここで本来は天候や混雑度をDBなどから取得する ---
        # 今回はダミーデータを生成する
        import random
        dummy_weather = random.randint(0, 2)
        dummy_congestion = random.randint(0, 4)
        # ----------------------------------------------------

        response_doc: RTDoc = {"s": spot_id, "w": dummy_weather, "c": dummy_congestion}
        
        # 内部状態を更新
        _state[spot_id] = response_doc

        # ★★★ フロントエンドに応答を返すためにDownlinkを送信 ★★★
        _publish_downlink(response_doc)

    except Exception as e:
        print(f"MQTTメッセージの処理中にエラーが発生しました: {e}")
        return

def _publish_downlink(payload: RTDoc):
    """ ★★★ TTNへDownlinkメッセージを送信する関数 ★★★ """
    if not _MQTT_CLIENT:
        print("【ERROR】 MQTTクライアント未初期化のためダウンリンク送信できません")
        return

    # フロントエンドが期待するJSON形式に変換
    payload_json = json.dumps(payload).encode("utf-8")
    # Base64にエンコード
    payload_b64 = base64.b64encode(payload_json).decode("utf-8")
    
    # TTNが要求するDownlinkメッセージの形式でラップする
    downlink_msg = {
        "downlinks": [{
            "f_port": 2, # フロントエンドの送信ポートと合わせる
            "frm_payload": payload_b64,
            "priority": "NORMAL"
        }]
    }
    
    try:
        downlink_json = json.dumps(downlink_msg)
        _MQTT_CLIENT.publish(MQTT_DOWNLINK_TOPIC, downlink_json, qos=1)
        print("【DEBUG】ダウンリンク送信成功")
    except Exception as e:
        print(f"【ERROR】ダウンリンク送信失敗: {e}")


def _mqtt_worker():
    global _MQTT_CLIENT
    print("MQTTワーカー開始")
    if mqtt is None or not all([TTN_APP_ID, TTN_DEVICE_ID]):
        print("MQTTクライアントが無効、またはTTNのIDが設定されていません。")
        return
        
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=f"backend-{os.getpid()}")
    print("MQTTクライアント生成完了")
    client.tls_set() # ★★★ TTNはTLS接続が必須 ★★★
    print("TLS設定完了")
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        print(f"MQTT認証情報設定完了: user={MQTT_USERNAME}")
    
    client.on_connect = _on_connect
    client.on_message = _on_message
    _MQTT_CLIENT = client
    
    try:
        print(f"MQTTブローカーに接続します: {MQTT_BROKER}:{MQTT_PORT}")
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        print("MQTT接続開始")
        client.loop_forever() # ★★★ loop_start/stopからforeverに変更して安定化 ★★★
    except Exception as e:
        # print(f"MQTTワーカーでエラー: {e}")
        import traceback
        print("MQTTワーカーで例外発生")
        print(traceback.format_exc())
    finally:
        print("MQTTワーカーが停止しました。")
        if client.is_connected():
            client.disconnect()


# (Thread, startup, shutdown, HTTP endpoints... 以下は変更なし)

_MQTT_THREAD: Optional[threading.Thread] = None
@router.on_event("startup")
def _startup_mqtt():
    print("【DEBUG】FastAPI startup イベント発火。MQTTワーカー起動中...")
    if mqtt is None:
        print("【ERROR】paho-mqttがimportできていません。")
        return
    global _MQTT_THREAD
    if _MQTT_THREAD and _MQTT_THREAD.is_alive():
        print("【DEBUG】MQTTワーカー既に起動中")
        return
    print("【DEBUG】MQTTスレッドを新規起動します")
    _MQTT_STOP.clear()
    _MQTT_THREAD = threading.Thread(target=_mqtt_worker, name="rt-mqtt", daemon=True)
    _MQTT_THREAD.start()
    threading.Thread(target=_status_monitor, daemon=True).start()

@router.on_event("shutdown")
def _shutdown_mqtt():
    if mqtt is None or not _MQTT_CLIENT: return
    _MQTT_CLIENT.disconnect()

@router.get("/spot/{spot_id}", response_class=JSONResponse, summary="最新のリアルタイム情報（極小JSON）")
def get_spot_rt(spot_id: str):
    item = _state.get(spot_id)
    if not item:
        return Response(status_code=204)
    return JSONResponse(content=item)

@router.post("/_mock/{spot_id}")
def _mock_push(spot_id: str, body: RTDoc):
    body["s"] = spot_id
    _state[spot_id] = body
    return {"ok": True}