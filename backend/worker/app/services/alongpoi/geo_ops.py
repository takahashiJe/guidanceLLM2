from __future__ import annotations

from typing import List, Dict, Iterable, Tuple

from shapely.geometry import LineString, Polygon, mapping
from shapely.ops import transform
from pyproj import Transformer


LonLat = Tuple[float, float]  # (lon, lat)


def _proj() -> Transformer:
    # EPSG:4326 → EPSG:3857（メートル系）
    return Transformer.from_crs(4326, 3857, always_xy=True)


def _unproj() -> Transformer:
    # EPSG:3857 → EPSG:4326
    return Transformer.from_crs(3857, 4326, always_xy=True)


def _slice_polyline(polyline: List[LonLat], start_idx: int, end_idx: int) -> List[LonLat]:
    start_idx = max(0, min(start_idx, len(polyline) - 1))
    end_idx = max(0, min(end_idx, len(polyline) - 1))
    if end_idx < start_idx:
        start_idx, end_idx = end_idx, start_idx
    seg = polyline[start_idx : end_idx + 1]
    # 1点しかない場合は直前の点を複製して LineString を作れるようにする
    if len(seg) == 1 and start_idx > 0:
        seg = [polyline[start_idx - 1], polyline[start_idx]]
    elif len(seg) == 1 and start_idx == 0 and len(polyline) > 1:
        seg = [polyline[0], polyline[1]]
    return seg


def _buffer_linestring_m(ls: LineString, meters: float) -> Polygon:
    """
    経度緯度の LineString を 3857 に変換してメートル単位で buffer。
    結果は 4326 に戻して返す。
    """
    to3857 = _proj().transform
    to4326 = _unproj().transform
    ls_m = transform(to3857, ls)
    poly_m = ls_m.buffer(meters)  # meters
    poly_lonlat = transform(to4326, poly_m)
    return poly_lonlat


def build_mode_buffers(
    polyline: List[List[float]],
    segments: List[Dict],
    buf_car_m: float = 300.0,
    buf_foot_m: float = 10.0,
) -> List[Polygon]:
    """
    モード別に polyline の区間を切り出して、それぞれを指定半径[m]でバッファ化した Polygon を返す。
    返却は EPSG:4326 (lon,lat) 座標の Shapely Polygon。
    """
    if not polyline or len(polyline) < 2:
        return []

    # polyline は [[lon,lat], ...]
    pl: List[LonLat] = [(p[0], p[1]) for p in polyline]
    polys: List[Polygon] = []

    for seg in segments:
        mode = seg.get("mode")
        s_idx = int(seg.get("start_idx", 0))
        e_idx = int(seg.get("end_idx", 0))
        coords = _slice_polyline(pl, s_idx, e_idx)
        if len(coords) < 2:
            continue
        ls = LineString(coords)
        radius = buf_car_m if mode == "car" else buf_foot_m
        poly = _buffer_linestring_m(ls, radius)
        polys.append(poly)

    return polys
