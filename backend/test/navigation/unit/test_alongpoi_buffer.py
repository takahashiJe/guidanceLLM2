import math
import pytest

from backend.worker.app.services.alongpoi.geo_ops import build_mode_buffers

def test_build_mode_buffers__car_300m_foot_10m(simple_polyline, simple_segments):
    polys = build_mode_buffers(simple_polyline, simple_segments, buf_car_m=300, buf_foot_m=10)
    assert len(polys) == 2  # car と foot のバッファ（セグメントに応じて少なくとも2つ）
    # 面積がゼロでないこと
    for p in polys:
        assert getattr(p, "area", 1.0) > 0.0

def test_build_mode_buffers__area_ratio(simple_polyline):
    # car のみと foot のみで比較（同じ線長なら面積は半径^2に概ね比例）
    car_only = [{"mode":"car","start_idx":0,"end_idx":3}]
    foot_only = [{"mode":"foot","start_idx":0,"end_idx":3}]
    polys_car = build_mode_buffers(simple_polyline, car_only, buf_car_m=300, buf_foot_m=10)
    polys_foot = build_mode_buffers(simple_polyline, foot_only, buf_car_m=300, buf_foot_m=10)

    area_car = sum(p.area for p in polys_car if hasattr(p, "area"))
    area_foot = sum(p.area for p in polys_foot if hasattr(p, "area"))

    # 300m と 10m → 半径比 30 → 面積比 ≈ 900
    assert area_car > area_foot * 100  # ゆるめの下限（実装差吸収）
