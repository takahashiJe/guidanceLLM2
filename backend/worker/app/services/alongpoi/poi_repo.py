from __future__ import annotations

import os
from typing import List, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from shapely.ops import unary_union

from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid
import logging

log = logging.getLogger(__name__)
_engine: Engine | None = None

def _clean_geoms(geoms):
    cleaned = []
    for g in geoms:
        if not isinstance(g, BaseGeometry):
            continue
        if g.is_empty:
            continue
        gg = make_valid(g)
        if not gg.is_valid:
            gg = gg.buffer(0)
        if gg.is_empty or not gg.is_valid:
            continue
        cleaned.append(gg)
    return cleaned

def _conn_url() -> str:
    host = os.getenv("STATIC_DB_HOST", "static-db")
    port = os.getenv("STATIC_DB_PORT", "5432")
    db   = os.getenv("STATIC_DB_NAME", "nav_static")
    user = os.getenv("STATIC_DB_USER", "nav_static")
    pwd  = os.getenv("STATIC_DB_PASSWORD", "nav_static")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_conn_url(), future=True)
    return _engine


def _union_wkt(polys) -> str:
    polys = _clean_geoms(polys)
    if not polys:
        log.warning("along buffers → all invalid/empty; skip POI query")
        return None
    for i, p in enumerate(polys):
        log.info(f"Polygon {i} WKT for union: {p.wkt}")
    mp = unary_union(polys)  # 4326 前提
    return mp.wkt


_SQL_QUERY = text(
    """
    SELECT spot_id, name, lon, lat, kind
    FROM poi_features_v
    WHERE ST_Intersects(
        geom,
        ST_GeomFromText(:wkt, 4326)
    )
    """
)


def query_pois(polys) -> List[Dict]:
    """
    ルートバッファ（Polygon群）に交差する POI（spots + facilities）を返す。
    返却: [{"spot_id","name","lon","lat","kind"}...]
    """
    wkt = _union_wkt(polys)
    if not wkt:
        return []  # ヒットなし
    try:
        eng = _get_engine()
    except Exception:
        return []

    try:
        with eng.connect() as conn:
            rows = conn.execute(_SQL_QUERY, {"wkt": wkt}).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        # ビュー未作成などの場合は空配列
        return []
