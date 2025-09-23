from backend.worker.app.services.alongpoi.reducer import reduce_hits_to_along_pois

def test_reduce_hits__assigns_leg_index_and_distance(simple_polyline, poi_hits_near_first_leg):
    # 2本のレッグ（0: car 0-1, 1: foot 1-3）を仮定。reducer 側で最近距離から leg_index を判定できること。
    result = reduce_hits_to_along_pois(poi_hits_near_first_leg, simple_polyline)
    assert len(result) >= 1
    first = result[0]
    assert "spot_id" in first and "distance_from_route_m" in first and "leg_index" in first
    assert first["distance_from_route_m"] >= 0
