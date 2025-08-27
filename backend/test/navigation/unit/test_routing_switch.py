import types
import pytest

from backend.worker.app.services.routing import osrm_client as oc
from backend.worker.app.services.routing.logic import build_legs_with_switch

class DummyRoute:
    def __init__(self, ok: bool, distance=1000.0, duration=600.0, coords=None):
        self.ok = ok
        self.distance = distance
        self.duration = duration
        self.geometry = {"type": "LineString", "coordinates": coords or [[139.9,39.2],[139.95,39.25]]}

def test_build_legs_with_switch__fallback_to_access_point(monkeypatch, sample_waypoints):
    # current → A 間は car 失敗
    # AP を返すフェイク: A 近傍の (lat,lon)
    def fake_osrm_route(profile, src, dst):
        if profile == "car":
            return DummyRoute(ok=False)
        return DummyRoute(ok=True, coords=[[139.94,39.24],[139.95,39.25]])

    monkeypatch.setattr(oc, "osrm_route", fake_osrm_route, raising=True)

    # nearest_access_point は A 近くを返す
    from backend.worker.app.services.routing import logic as rlogic
    monkeypatch.setattr(rlogic, "nearest_access_point", lambda dest: (dest[0], dest[1]-0.02), raising=True)

    legs = build_legs_with_switch(sample_waypoints[:2])  # current → A
    # car 失敗→ car(src→AP) + foot(AP→A) の2レッグになるはず
    assert len(legs) == 2
    assert legs[0]["mode"] == "car"
    assert legs[1]["mode"] == "foot"
    assert legs[0]["distance"] > 0
    assert legs[1]["distance"] > 0

def test_build_legs_with_switch__car_direct_success(monkeypatch, sample_waypoints):
    def fake_osrm_route(profile, src, dst):
        return DummyRoute(ok=True)
    monkeypatch.setattr(oc, "osrm_route", fake_osrm_route, raising=True)

    legs = build_legs_with_switch(sample_waypoints[:2])
    assert len(legs) == 1
    assert legs[0]["mode"] == "car"
