import pytest

def test_alongpoi_endpoint__extracts_pois(monkeypatch, client_alongpoi, simple_polyline, simple_segments, poi_hits_near_first_leg):
    # geo_ops と poi_repo, reducer をスタブ化
    from backend.worker.app.services.alongpoi import geo_ops
    from backend.worker.app.services.alongpoi import reducer
    # 仮のポリゴン（area 属性だけを持つ簡易オブジェクト）
    class DummyPoly:
        def __init__(self, area): self.area = area

    monkeypatch.setattr(geo_ops, "build_mode_buffers",
                        lambda polyline, segments, buf_car_m=300, buf_foot_m=10: [DummyPoly(1.0), DummyPoly(0.1)],
                        raising=True)

    # poi_repo は main 側で import している前提で，そこに hits を返す関数がある想定にする
    # ここでは reducer 側だけで完結させるため，reduce がそのまま hits を POI 出力に変換する挙動をスタブ
    def fake_reduce_hits_to_along_pois(hits, polyline):
        out = []
        for i, h in enumerate(hits):
            out.append({
                "spot_id": h["spot_id"],
                "name": h["name"],
                "leg_index": 0,
                "distance_from_route_m": 80 + i  # 適当
            })
        return out

    monkeypatch.setattr(reducer, "reduce_hits_to_along_pois", fake_reduce_hits_to_along_pois, raising=True)

    # main 内で参照する「POI を得る関数」を直接スタブ（関数名は実装で合わせてください）
    import backend.worker.app.services.alongpoi.main as along_main
    monkeypatch.setattr(along_main, "query_pois_in_buffers", lambda polys: poi_hits_near_first_leg, raising=False)

    body = {
        "polyline": simple_polyline,
        "segments": simple_segments,
        "buffer": {"car": 300, "foot": 10}
    }
    res = client_alongpoi.post("/along", json=body)
    assert res.status_code == 200
    data = res.json()

    assert "pois" in data and data["count"] == len(data["pois"])
    assert len(data["pois"]) == len(poi_hits_near_first_leg)
    assert {"spot_id","name","leg_index","distance_from_route_m"} <= set(data["pois"][0].keys())
