import json
import respx
import httpx

def _routing_resp_simple():
    legs = [
        {"mode":"car","from_idx":0,"to_idx":1,"distance":1200,"duration":120,
         "geometry":{"type":"LineString","coordinates":[[139.90,39.20],[139.93,39.23]]}},
        {"mode":"car","from_idx":1,"to_idx":2,"distance":5000,"duration":420,
         "geometry":{"type":"LineString","coordinates":[[139.93,39.23],[139.95,39.25]]}},
    ]
    fc = {
        "type":"FeatureCollection",
        "features":[{"type":"Feature","properties":{"mode":l["mode"]},"geometry":l["geometry"]} for l in legs]
    }
    poly = [[139.90,39.20],[139.93,39.23],[139.95,39.25]]
    segments = [
        {"mode":"car","start_idx":0,"end_idx":1},
        {"mode":"car","start_idx":1,"end_idx":2},
    ]
    return {"feature_collection": fc, "legs": legs, "polyline": poly, "segments": segments}

def _many_pois(n=50):
    return {
        "pois": [
            {"spot_id": f"D{i}", "name": f"Spot D{i}", "leg_index": i % 2, "distance_from_route_m": 50 + (i % 30)}
            for i in range(n)
        ],
        "count": n
    }

@respx.mock
def test_nav_plan_large_poi_list_perf(nav_client):
    # waypoints は最小構成（current→A→current でもよい）
    waypoints = [
        {"lat": 39.2000, "lon": 139.9000, "spot_id": "current"},
        {"lat": 39.3000, "lon": 139.9500, "spot_id": "A"},
        {"lat": 39.2000, "lon": 139.9000, "spot_id": "current"},
    ]

    respx.post("http://routing/route").mock(return_value=httpx.Response(200, json=_routing_resp_simple()))
    respx.post("http://alongpoi/along").mock(return_value=httpx.Response(200, json=_many_pois(50)))

    # LLM は大量スポットでも単純生成
    def llm_reply(request: httpx.Request):
        payload = json.loads(request.content.decode())
        spots = payload["spots"]
        lang = payload["language"]
        return httpx.Response(200, json={"items": [{"spot_id": s["spot_id"], "text": f"[{lang}] {s['spot_id']}"} for s in spots]})
    respx.post("http://llm/describe").mock(side_effect=llm_reply)

    # voice も一定の固定レスポンス
    def voice_reply(request: httpx.Request):
        p = json.loads(request.content.decode())
        return httpx.Response(200, json={"audio_url": f"/packs/GUID/{p['spot_id']}.{p['language']}.mp3", "bytes": 500, "duration_s": 5.0})
    respx.post("http://voice/synthesize").mock(side_effect=voice_reply)

    body = {"language":"ja","waypoints": waypoints, "buffers":{"car":300,"foot":10}}
    r = nav_client.post("/plan", json=body)
    assert r.status_code == 200
    data = r.json()

    # assets 数は A (計画スポット) + 沿道 50 = 51 のはず
    # nav の仕様で重複除外が入るなら、その分を考慮（ここでは重複しないID使用）
    assert len(data["assets"]) == 1 + 50
    # いくつかの代表 spot の asset をチェック
    any_asset = next(a for a in data["assets"] if a["spot_id"] == "A")
    assert any_asset["audio_url"].endswith(".ja.mp3")
