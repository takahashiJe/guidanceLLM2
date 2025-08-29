import json
import respx
import httpx

def _routing_resp_mix():
    # A→B だけ徒歩セグメントを含む例（AP 経由は routing サービス内で処理済みの前提）
    legs = [
        {"mode":"car","from_idx":0,"to_idx":1,"distance":1200,"duration":120,
         "geometry":{"type":"LineString","coordinates":[[139.90,39.20],[139.93,39.23]]}},
        {"mode":"foot","from_idx":1,"to_idx":2,"distance":900,"duration":900,
         "geometry":{"type":"LineString","coordinates":[[139.93,39.23],[139.95,39.25]]}},
        {"mode":"car","from_idx":2,"to_idx":3,"distance":5000,"duration":420,
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
        {"mode":"foot","start_idx":1,"end_idx":2},
        {"mode":"car","start_idx":2,"end_idx":3},
        {"mode":"car","start_idx":3,"end_idx":4},
    ]
    return {"feature_collection": fc, "legs": legs, "polyline": poly, "segments": segments}

def _along_resp_for_mix():
    # 徒歩区間（leg_index=1）に近い POI を含める
    return {
        "pois": [
            {"spot_id":"D","name":"Spot D","leg_index":1,"distance_from_route_m":9},
            {"spot_id":"E","name":"Spot E","leg_index":0,"distance_from_route_m":250}
        ],
        "count": 2
    }

@respx.mock
def test_nav_plan_car_then_foot_mix(nav_client, sample_waypoints):
    respx.post("http://routing/route").mock(return_value=httpx.Response(200, json=_routing_resp_mix()))
    respx.post("http://alongpoi/along").mock(return_value=httpx.Response(200, json=_along_resp_for_mix()))

    def llm_reply(request: httpx.Request):
        payload = json.loads(request.content.decode())
        spots = payload["spots"]
        lang = payload["language"]
        items = [{"spot_id": s["spot_id"], "text": f"[{lang}] {s.get('name', s['spot_id'])}"} for s in spots]
        return httpx.Response(200, json={"items": items})
    respx.post("http://llm/describe").mock(side_effect=llm_reply)

    def voice_reply(request: httpx.Request):
        p = json.loads(request.content.decode())
        return httpx.Response(200, json={"audio_url": f"/packs/GUID/{p['spot_id']}.{p['language']}.mp3", "bytes": 1000, "duration_s": 10.0})
    respx.post("http://voice/synthesize").mock(side_effect=voice_reply)

    body = {"language":"ja","waypoints": sample_waypoints, "buffers":{"car":300,"foot":10}}
    r = nav_client.post("/plan", json=body)
    assert r.status_code == 200
    data = r.json()

    # レッグモード配列が car, foot, car, car になっていること
    assert [l["mode"] for l in data["legs"]] == ["car","foot","car","car"]

    # 徒歩レッグ(leg_index=1)に紐づく POI が結果に含まれる
    along_leg_idxs = {p["leg_index"] for p in data["along_pois"]}
    assert 1 in along_leg_idxs

    # assets は A,B,C + D,E
    assert sorted([a["spot_id"] for a in data["assets"]]) == ["A","B","C","D","E"]
