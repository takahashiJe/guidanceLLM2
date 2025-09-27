from __future__ import annotations

from typing import Dict, List, Tuple, Literal

from backend.worker.app.services.routing import osrm_client as oc
from backend.worker.app.services.routing.osrm_client import OsrmRouteResult
from backend.worker.app.services.routing import access_point_repo as ap_repo

import logging # ファイルの先頭に追加
logger = logging.getLogger(__name__)

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
    - 徒歩で目的地に到着した場合、次のルート計算の始点は車両が待機している access_point にする。
    """
    legs: List[Dict] = []
    n = len(waypoints)
    if n < 2:
        return legs

    # 車両の現在位置を追跡するための変数
    # 初期値は最初のウェイポイント
    car_location = waypoints[0]

    for i in range(n - 1):
        # ルート計算の始点は、常に車両の現在位置
        src = car_location
        # 目的地は、元のウェイポイントリストの次の地点
        dst = waypoints[i + 1]

        # 1) まず car 直行を試す
        r_car_direct = oc.osrm_route("car", src, dst)
        if getattr(r_car_direct, "ok", False):
            legs.append(_result_to_leg("car", r_car_direct, i, i + 1))
            # 車で直接到達できたので、車両位置を目的地に更新
            car_location = dst
            continue

        # 2) 車で直行できない場合: access_point を経由する
        ap = nearest_access_point(dst)

        # 車両の現在地(src)からaccess_pointまでの車ルート
        r_car_to_ap = oc.osrm_route("car", src, ap)
        legs.append(_result_to_leg("car", r_car_to_ap, i, i + 1))
        
        # 車両はaccess_pointで待機するので、車両位置を更新
        car_location = ap

        # access_pointから目的地までの徒歩ルート
        r_foot_ap_to_dst = oc.osrm_route("foot", ap, dst)
        legs.append(_result_to_leg("foot", r_foot_ap_to_dst, i, i + 1)) # インデックスを修正
        # ユーザーは徒歩で目的地に移動するが、車両はAPに残る。
        # 次のループの始点は更新された car_location (つまり ap) となる。

    logger.info(f"Generated legs for routing: {legs}")
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
