from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Tuple
import math

import httpx

OSRM_CAR_URL = os.getenv("OSRM_CAR_URL", "http://osrm-car:5000")
OSRM_FOOT_URL = os.getenv("OSRM_FOOT_URL", "http://osrm-foot:5000")

CAR_ARRIVAL_TOLERANCE_METERS = 50.0
"""
車ルートの許容誤差（メートル）。
OSRMは車道から外れた座標（例：滝）を指定されても、最寄りの車道上の点を終点とするルートを「成功(Ok)」として返す。
この距離が閾値を超えた場合、「車では到達失敗」とみなす。
"""

@dataclass
class OsrmRouteResult:
    ok: bool
    distance: float = 0.0
    duration: float = 0.0
    geometry: dict | None = None
    raw: dict | None = None


def _pick_base(profile: Literal["car", "foot"]) -> str:
    if profile == "foot":
        return OSRM_FOOT_URL.rstrip("/")
    return OSRM_CAR_URL.rstrip("/")


def _to_lonlat(coord: Tuple[float, float]) -> Tuple[float, float]:
    # 入力は (lat, lon) 前提 → (lon, lat) に並べ替え
    lat, lon = coord
    return float(lon), float(lat)

def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    2つの緯度経度間の距離をメートル単位で計算する（Haversineの公式）。
    """
    R = 6371000  # 地球の半径（メートル）

    rad_lat1 = math.radians(lat1)
    rad_lat2 = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2) + \
        (math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

def build_osrm_url(
    profile: Literal["car", "foot"],
    src: Tuple[float, float],
    dst: Tuple[float, float],
    *,
    overview: str = "full",
    geometries: str = "geojson",
    steps: bool = True,
    alternatives: int = 0,
) -> str:
    base = _pick_base(profile)
    s_lon, s_lat = _to_lonlat(src)
    d_lon, d_lat = _to_lonlat(dst)
    coords = f"{s_lon},{s_lat};{d_lon},{d_lat}"
    params = f"overview={overview}&geometries={geometries}&steps={'true' if steps else 'false'}&alternatives={alternatives}"
    return f"{base}/route/v1/{profile}/{coords}?{params}"


def osrm_route(
    profile: Literal["car", "foot"],
    src: Tuple[float, float],
    dst: Tuple[float, float],
    *,
    timeout: float = 15.0,
) -> OsrmRouteResult:
    """
    OSRM に問い合わせて最良ルートを 1 本返す。
    失敗時は ok=False の結果を返す（例外は飲み込む）。
    """
    url = build_osrm_url(profile, src, dst)
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url)
        if r.status_code != 200:
            return OsrmRouteResult(ok=False, raw={"status_code": r.status_code, "text": r.text})
        data = r.json()
        code = data.get("code")
        if code != "Ok" or not data.get("routes"):
            return OsrmRouteResult(ok=False, raw=data)
        route = data["routes"][0]
        geometry = route.get("geometry") # 先にジオメトリを取得

        # 車(car)プロファイルの場合のみ、「到達距離の検証」を行う
        if profile == "car":
            # geometryがGeoJSON形式(dict)であり、座標(coordinates)リストを持つか検証
            if (
                isinstance(geometry, dict) 
                and geometry.get("type") == "LineString"
                and geometry.get("coordinates")
            ):
                try:
                    # ルートの実際の終点座標 [lon, lat] を取得
                    coordinates = geometry["coordinates"]
                    route_end_lon, route_end_lat = coordinates[-1]
                    
                    # 本来の目的地座標 (lat, lon)
                    intended_dst_lat, intended_dst_lon = dst

                    # 距離（メートル）を計算
                    distance_to_target = _haversine_distance_m(
                        lat1=intended_dst_lat,
                        lon1=intended_dst_lon,
                        lat2=route_end_lat,
                        lon2=route_end_lon
                    )

                    # 距離が許容誤差（50m）を超えている場合
                    if distance_to_target > CAR_ARRIVAL_TOLERANCE_METERS:
                        logger.warning(
                            f"Car route 'Ok' but missed target by {distance_to_target:.1f}m. "
                            f"(Tolerance: {CAR_ARRIVAL_TOLERANCE_METERS}m). Dst seems off-road. "
                            f"Overriding to failure to trigger switch logic. (URL: {url})"
                        )
                        # 許容誤差を超えたため、OSRMが 'Ok' と返しても「失敗」として上書きする
                        return OsrmRouteResult(ok=False, raw=data)

                except Exception as e:
                    # 距離検証中に予期せぬエラー（座標リストが空など）が発生した場合
                    logger.error(f"Failed during arrival distance validation: {e}. Assuming failure. (URL: {url})")
                    return OsrmRouteResult(ok=False, raw={"error": repr(e), "url": url})
            
            elif not geometry:
                 # ジオメトリが無い場合は（通常あり得ないが）念のため失敗扱い
                logger.warning(f"Car route 'Ok' but no geometry found. Assuming failure. (URL: {url})")
                return OsrmRouteResult(ok=False, raw=data)
        return OsrmRouteResult(
            ok=True,
            distance=float(route.get("distance", 0.0)),
            duration=float(route.get("duration", 0.0)),
            geometry=route.get("geometry"),
            raw=data,
        )
    except Exception as e:
        return OsrmRouteResult(ok=False, raw={"error": repr(e), "url": url})
