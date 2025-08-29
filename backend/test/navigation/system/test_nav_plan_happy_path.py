import json
import uuid
import respx
import httpx

def _routing_resp():
    legs = [
        {"mode":"car","from_idx":0,"to_idx":1,"distance":1200,"duration":120,
         "geometry":{"type":"LineString","coordinates":[[139.90,39.20],[139.93,39.23]]}},
        {"mode":"car","from_idx":1,"to_idx":2,"distance":5000,"duration":420,
         "geometry":{"type":"LineString","coordinates":[[139.93,39.23],[139.95,39.25]]}},
        {"mode":"car","from_idx":2,"to_idx":3,"distance":7000,"duration":600,
         "geometry":{"type":"LineString","coordinates":[[139.95,39.25],[139.96,39.25]]}},
        {"mode":"car","from_idx":3,"to_idx":4,"distance":7000,"duration":600,
         "geometry":{"type":"LineString","coordinates":[[139.96,39.25],[139.90,39.20]]}},
    ]
    fc = {
        "type":"FeatureCollection",
        "features":[{"type":"Feature","properties":{"mode":l["mode"]},"geometry":l["geometry"]} for l in legs]
    }
    poly = [[139.90,39.20],[139.93,39.23],[139.95,39.25],[139.96,39.25],[139.90,39.20]]
    segments = [
        {"mode":"car","start_idx":0,"end_idx":1},
        {"mode":"car","start_idx":1,"end_idx":2},
        {"mode":"car","start_idx":2,"end_idx":3},
        {"mode":"car","start_idx":3,"end_idx":4},
    ]
    return {"feature_collection": fc, "legs": legs, "polyline": poly, "segments": segments}

def _along_resp():
    return {
        "pois": [
            {"spot_id":"D","name":"Spot D","leg_index":0,"distance_from_route_m":85},
            {"spot_id":"E","name":"Spot E","leg_index":2,"distance_from_route_m":120}
        ],
        "count": 2
    }

def _llm_resp(spots, lang):
    return {
        "items": [{"spot_id": s["spot_id"], "text": f"[{lang}] {s.get('name', s['spot_id'])} narration"} for s in spots]
    }

def _voice_cb(request: httpx.Request):
    payload = json.loads(request.content.decode())
    spot_id = payload["spot_id"]
    lang = payload["language"]
    body = {"audio_url": f"/packs/GUID/{spot_id}.{lang}.mp3", "bytes": 8_4231, "duration_s": 58.3}
    return httpx.Response(200, json=body)

@respx.mock
def test_nav_plan_happy_path(nav_client, sample_waypoints):
    # 下流サービスの HTTP をモック
    respx.post("http://routing/route").mock(return_value=httpx.Response(200, json=_routing_resp()))
    # along は polyline/segments を受ける想定だが、ここではレスポンスだけで十分
    respx.post("http://alongpoi/along").mock(return_value=httpx.Response(200, json=_along_resp()))
    # llm は A,B,C,D,E の5件を生成
    def llm_reply(request: httpx.Request):
        lang = json.loads(request.content.decode())["language"]
        spots = json.loads(request.content.decode())["spots"]
        return httpx.Response(200, json=_llm_resp(spots, lang))
    respx.post("http://llm/describe").mock(side_effect=llm_reply)
    # voice は spot ごとにコールバックで URL を返す
    respx.post("http://voice/synthesize").mock(side_effect=_voice_cb)

    body = {"language":"ja","waypoints": sample_waypoints, "buffers":{"car":300,"foot":10}}
    r = nav_client.post("/plan", json=body)
    assert r.status_code == 200
    data = r.json()

    # 返却の基本要素
    assert "pack_id" in data and isinstance(data["pack_id"], str)
    assert "route" in data and data["route"]["type"] == "FeatureCollection"
    assert "legs" in data and len(data["legs"]) == 4
    assert "along_pois" in data and len(data["along_pois"]) == 2
    assert "assets" in data

    # assets は A,B,C + D,E = 5件（順序は問わない）
    spot_ids = sorted([a["spot_id"] for a in data["assets"]])
    assert spot_ids == ["A","B","C","D","E"]

    # 各アセットに text_url と audio_url が揃う
    for a in data["assets"]:
        assert a["audio_url"].endswith(f"/packs/{data['pack_id']}/{a['spot_id']}.ja.mp3") or a["audio_url"].endswith(f"/packs/GUID/{a['spot_id']}.ja.mp3")
        assert a.get("text_url") is None or a["text_url"].endswith(f"/packs/{data['pack_id']}/{a['spot_id']}.ja.md")
