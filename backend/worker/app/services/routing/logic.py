from __future__ import annotations

from typing import Dict, List, Tuple, Literal

from shapely.geometry import Point, LineString
from shapely.ops import transform
from pyproj import Transformer

from backend.worker.app.services.routing import osrm_client as oc
from backend.worker.app.services.routing.osrm_client import OsrmRouteResult
from backend.worker.app.services.routing import access_point_repo as ap_repo
from backend.worker.app.services.routing.spot_repo import SpotRepo, SpotInfo

import logging
logger = logging.getLogger(__name__)

Coord = Tuple[float, float]  # (lat, lon)

def _proj() -> Transformer:
    """WGS84 (EPSG:4326) からウェブメルカトル (EPSG:3857) へ変換する"""
    return Transformer.from_crs(4326, 3857, always_xy=True)


def build_waypoints_info(spot_ids: List[str], language: str, polyline: List[List[float]]) -> List[Dict]:
    """
    NAVの _build_spot_refs と _reduce_hits_to_along_pois_local の機能を統合した関数。
    1. spot_idからスポットの基本情報(名前,座標など)をDBから取得。
    2. 各スポットがルート(polyline)上のどの点に最も近いかを計算し、情報を付与する。
    """
    # 1. スポットの基本情報を取得 (_build_spot_refs に相当)
    repo = SpotRepo()
    spot_info_map = repo.get_spots_by_ids(spot_ids, language)

    # 2. polylineとの最近接点情報を計算 (_reduce_hits_to_along_pois_local に相当)
    if not spot_info_map or not polyline or len(polyline) < 2:
        return []

    # 計算準備: polylineをメートル座標系(3857)に変換
    to3857 = _proj().transform
    line_lonlat = [(p[0], p[1]) for p in polyline]
    line_3857 = transform(to3857, LineString(line_lonlat))

    # WaypointInfoのリストを作成
    waypoints_info = []
    for spot_id, info in spot_info_map.items():
        if info.lat is None or info.lon is None:
            continue

        pt_3857 = transform(to3857, Point(info.lon, info.lat))
        
        # ルート全体との距離
        distance_m = float(line_3857.distance(pt_3857))
        
        # ルート上で最も近い点のインデックスを探す
        nearest_idx = 0
        min_dist_to_point = float("inf")
        for i, p_lonlat in enumerate(line_lonlat):
            p_3857 = transform(to3857, Point(p_lonlat))
            d = p_3857.distance(pt_3857)
            if d < min_dist_to_point:
                min_dist_to_point = d
                nearest_idx = i

        waypoints_info.append({
            "spot_id": info.spot_id,
            "name": info.name,
            "lon": info.lon,
            "lat": info.lat,
            "nearest_idx": nearest_idx,
            "distance_m": distance_m,
        })
    
    # ユーザーが指定した順序に並べ替え
    ordered_info = sorted(waypoints_info, key=lambda x: spot_ids.index(x['spot_id']))
    return ordered_info

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
