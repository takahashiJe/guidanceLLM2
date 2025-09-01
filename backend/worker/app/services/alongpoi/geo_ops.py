from __future__ import annotations

from typing import List, Dict, Iterable, Tuple

from shapely.geometry import LineString, Polygon, mapping, MultiLineString
from shapely.validation import make_valid
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
    poly_m = ls_m.buffer(meters, join_style='bevel')  # meters
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

        print("---" * 10)
        print(f"Original polygon generated for mode '{mode}'.")
        print(f"Is original polygon valid? -> {poly.is_valid}")
        # WKT形式でジオメトリを出力すると、外部ツールで可視化も可能
        print(f"Original WKT: {poly.wkt}") 
        print("---" * 10)

        polys.append(poly)

    # return polys
    raw_polys = polys  # 既存結果
    cleaned = []
    for p in raw_polys:
        if p.is_empty:
            continue
        
        print("!!!" * 10)
        print("Found invalid polygon, attempting to clean...")

        pp = make_valid(p)
        if not pp.is_valid:
            pp = pp.buffer(0)
        
        print(f"Is cleaned polygon valid? -> {pp.is_valid}")
        if not pp.is_valid:
            print("Cleaning FAILED.")
            print(f"Invalid WKT after cleaning: {pp.wkt}")
        else:
            print("Cleaning SUCCEEDED.")
        print("!!!" * 10)

        if pp.is_empty or not pp.is_valid:
            continue
        cleaned.append(pp)
    return cleaned

def build_mode_multilines(
    polyline: List[LonLat],
    segments: List[Dict],
) -> Dict[str, MultiLineString | None]:
    """
    segments の各区間を mode ごとに切り出し，car/foot の MultiLineString を返す．
    """
    # lon,lat の正規化
    pl = [(float(lon), float(lat)) for lon, lat in polyline]

    car_lines: list[LineString] = []
    foot_lines: list[LineString] = []

    for seg in segments:
        mode = seg.get("mode")
        s_idx = int(seg.get("start_idx", 0))
        e_idx = int(seg.get("end_idx", 0))
        coords = _slice_polyline(pl, s_idx, e_idx)
        if len(coords) < 2:
            continue
        ls = LineString(coords)
        if mode == "car":
            car_lines.append(ls)
        else:
            foot_lines.append(ls)

    return {
        "car":  MultiLineString(car_lines)  if car_lines  else None,
        "foot": MultiLineString(foot_lines) if foot_lines else None,
    }