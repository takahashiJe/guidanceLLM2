from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Tuple

import httpx

OSRM_CAR_URL = os.getenv("OSRM_CAR_URL", "http://osrm-car:5000")
OSRM_FOOT_URL = os.getenv("OSRM_FOOT_URL", "http://osrm-foot:5000")


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
        return OsrmRouteResult(
            ok=True,
            distance=float(route.get("distance", 0.0)),
            duration=float(route.get("duration", 0.0)),
            geometry=route.get("geometry"),
            raw=data,
        )
    except Exception as e:
        return OsrmRouteResult(ok=False, raw={"error": repr(e), "url": url})
