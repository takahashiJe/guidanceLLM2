from __future__ import annotations

from typing import Dict, List, Tuple, Literal

from backend.worker.app.services.routing.osrm_client import osrm_route, OsrmRouteResult
from backend.worker.app.services.routing import access_point_repo as ap_repo


Coord = Tuple[float, float]  # (lat, lon)


def _result_to_leg(
    mode: Literal["car", "foot"],
    res: OsrmRouteResult,
    from_idx: int,
    to_idx: int,
) -> Dict:
    return {
        "mode": mode,
        "from_idx": from_idx,
        "to_idx": to_idx,
        "distance": float(getattr(res, "distance", 0.0)),
        "duration": float(getattr(res, "duration", 0.0)),
        "geometry": getattr(res, "geometry", {"type": "LineString", "coordinates": []}) or {
            "type": "LineString",
            "coordinates": [],
        },
    }


def nearest_access_point(dest: Coord) -> Coord:
    """
    目的地近傍の access_point を返す。
    DB が使えない場合は「目的地にわずかにズラした点」を返してでも動かす。
    """
    lat, lon = dest
    ap = ap_repo.get_nearest_access_point(lat, lon)
    if ap:
        return (ap.lat, ap.lon)
    # フォールバック（DB 非稼働時）：東に 0.01 度オフセット
    return (lat, lon + 0.01)


def build_legs_with_switch(waypoints: List[Coord]) -> List[Dict]:
    """
    連続する waypoint ペアでレッグを構築。
    - car 直行が取れたら car レッグ。
    - 取れなければ dest 近傍の access_point を経由して car(src→AP) + foot(AP→dest)。
      （car(src→AP) が失敗しても、AP→dest の foot は実施する）
    返却する leg は dict（routing.main の Pydantic と互換）。
    """
    legs: List[Dict] = []
    n = len(waypoints)
    if n < 2:
        return legs

    for i in range(n - 1):
        src = waypoints[i]
        dst = waypoints[i + 1]

        # 1) まず car 直行を試す
        r_car_direct = osrm_route("car", src, dst)
        if getattr(r_car_direct, "ok", False):
            legs.append(_result_to_leg("car", r_car_direct, i, i + 1))
            continue

        # 2) AP 経由（car: src→AP, foot: AP→dest）
        ap = nearest_access_point(dst)

        r_car_to_ap = osrm_route("car", src, ap)
        # car が失敗でもダミーとして追加（距離は 0 の可能性もある）
        legs.append(_result_to_leg("car", r_car_to_ap, i, i))  # from_idx は src、to_idx は AP 仮想点として i を再利用

        r_foot_ap_to_dst = osrm_route("foot", ap, dst)
        legs.append(_result_to_leg("foot", r_foot_ap_to_dst, i, i + 1))

    return legs


def stitch_to_geojson(legs: List[Dict]) -> Tuple[Dict, List[List[float]], List[Dict]]:
    """
    leg 群の LineString を連結し、FeatureCollection, polyline（座標列）, segments(インデックス範囲) を返す。
    - polyline: [[lon,lat], ...]
    - segments: [{"mode","start_idx","end_idx"}]
    """
    feature_list: List[Dict] = []
    polyline: List[List[float]] = []
    segments: List[Dict] = []

    for leg in legs:
        geom = leg.get("geometry") or {}
        coords = list((geom.get("coordinates") or []))
        if not coords:
            # 空でもセグメントを確保（インデックスは現状維持）
            seg = {"mode": leg["mode"], "start_idx": max(len(polyline) - 1, 0), "end_idx": max(len(polyline) - 1, 0)}
            segments.append(seg)
            feature_list.append({"type": "Feature", "properties": {"mode": leg["mode"]}, "geometry": geom or {"type": "LineString", "coordinates": []}})
            continue

        # start index
        if not polyline:
            start_idx = 0
            polyline.extend(coords)
        else:
            # 最後の点と最初の点が同じなら重複を避ける
            if polyline[-1] == coords[0]:
                start_idx = len(polyline) - 1
                polyline.extend(coords[1:])
            else:
                start_idx = len(polyline)
                polyline.extend(coords)

        end_idx = len(polyline) - 1
        segments.append({"mode": leg["mode"], "start_idx": start_idx, "end_idx": end_idx})

        feature_list.append(
            {
                "type": "Feature",
                "properties": {
                    "mode": leg["mode"],
                    "from_idx": leg.get("from_idx"),
                    "to_idx": leg.get("to_idx"),
                    "distance": leg.get("distance"),
                    "duration": leg.get("duration"),
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )

    fc = {"type": "FeatureCollection", "features": feature_list}
    return fc, polyline, segments
