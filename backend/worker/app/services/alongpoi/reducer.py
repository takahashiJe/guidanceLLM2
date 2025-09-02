from __future__ import annotations

from typing import List, Dict, Tuple

from shapely.geometry import Point, LineString
from shapely.ops import transform
from pyproj import Transformer


def _proj() -> Transformer:
    return Transformer.from_crs(4326, 3857, always_xy=True)


def reduce_hits_to_along_pois(hits: List[Dict], polyline: List[List[float]]) -> List[Dict]:
    """
    DB等から得たヒット（少なくとも spot_id, lon, lat を含む dict 群）を、
    ルート polyline に基づいて
      - ルート最近距離 [m]
      - 属する線分 index（leg_index）
    を付与して返す。
    """
    if not hits or not polyline or len(polyline) < 2:
        return []

    to3857 = _proj().transform

    # ルートを 3857 に写像
    line_lonlat = [(p[0], p[1]) for p in polyline]
    line_3857 = transform(to3857, LineString(line_lonlat))

    # 各「線分」（2点間） 3857 表現を準備
    segs_3857 = []
    for i in range(len(line_lonlat) - 1):
        seg = LineString([line_lonlat[i], line_lonlat[i + 1]])
        segs_3857.append(transform(to3857, seg))

    out: List[Dict] = []
    for h in hits:
        lon, lat = float(h["lon"]), float(h["lat"])
        pt_3857 = transform(to3857, Point(lon, lat))

        # 最近距離 [m]
        dist_m = float(line_3857.distance(pt_3857))

        # 最近線分の index
        best_idx = 0
        best_d = float("inf")
        for i, seg in enumerate(segs_3857):
            d = seg.distance(pt_3857)
            if d < best_d:
                best_d = d
                best_idx = i

        distance_m = float(h.get("distance_m", dist_m))  # SQLの値があれば優先
        out.append(
            {
                "spot_id": h.get("spot_id"),
                "name": h.get("name"),
                "lon": float(h.get("lon")) if "lon" in h else None,
                "lat": float(h.get("lat")) if "lat" in h else None,
                "kind": h.get("kind"),
                "leg_index": int(best_idx),
                "distance_m": distance_m,
                "source_segment_mode": h.get("source_segment_mode"),
            }
        )

    return out
