import pytest

def test_route_endpoint__car_then_foot(monkeypatch, client_routing, sample_waypoints):
    # routing.logic の核となる2関数をスタブ化してエンドポイントの I/O を検証
    from backend.worker.app.services.routing import logic as rlogic

    def fake_build_legs_with_switch(wps):
        # current→A を car，A→B を foot，B→C を car，C→current を car，の例
        return [
            {"mode":"car","from_idx":0,"to_idx":1,"distance":1200,"duration":120,
             "geometry":{"type":"LineString","coordinates":[[139.90,39.20],[139.93,39.23]]}},
            {"mode":"foot","from_idx":1,"to_idx":2,"distance":800,"duration":900,
             "geometry":{"type":"LineString","coordinates":[[139.93,39.23],[139.95,39.25]]}},
            {"mode":"car","from_idx":2,"to_idx":3,"distance":5000,"duration":420,
             "geometry":{"type":"LineString","coordinates":[[139.95,39.25],[139.96,39.25]]}},
            {"mode":"car","from_idx":3,"to_idx":4,"distance":7000,"duration":600,
             "geometry":{"type":"LineString","coordinates":[[139.96,39.25],[139.90,39.20]]}},
        ]

    def fake_stitch_to_geojson(legs):
        coords = [[139.90,39.20],[139.93,39.23],[139.95,39.25],[139.96,39.25],[139.90,39.20]]
        fc = {
            "type":"FeatureCollection",
            "features":[{"type":"Feature","properties":{"mode":l["mode"]},"geometry":l["geometry"]} for l in legs]
        }
        segments = [
            {"mode":"car","start_idx":0,"end_idx":1},
            {"mode":"foot","start_idx":1,"end_idx":2},
            {"mode":"car","start_idx":2,"end_idx":3},
            {"mode":"car","start_idx":3,"end_idx":4},
        ]
        return fc, coords, segments

    monkeypatch.setattr(rlogic, "build_legs_with_switch", fake_build_legs_with_switch, raising=True)
    monkeypatch.setattr(rlogic, "stitch_to_geojson", fake_stitch_to_geojson, raising=True)

    body = {"waypoints": sample_waypoints, "car_to_trailhead": True}
    res = client_routing.post("/route", json=body)
    assert res.status_code == 200
    data = res.json()

    assert "feature_collection" in data and data["feature_collection"]["type"] == "FeatureCollection"
    assert "legs" in data and len(data["legs"]) == 4
    assert "polyline" in data and len(data["polyline"]) >= 2
    assert "segments" in data and len(data["segments"]) == 4

    # モードのシーケンスを確認
    modes = [l["mode"] for l in data["legs"]]
    assert modes == ["car","foot","car","car"]


def test_route_endpoint__bad_request(monkeypatch, client_routing):
    # waypoints が少な過ぎる場合など，エラーを返すこと（実装側の 400 を確認）
    body = {"waypoints": [{"lat": 39.2, "lon": 139.9}], "car_to_trailhead": True}
    res = client_routing.post("/route", json=body)
    assert res.status_code in (400, 422)  # 実装次第で validation error(422) でも可
