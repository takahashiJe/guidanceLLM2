from __future__ import annotations

import os
from typing import List, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from shapely.geometry import mapping
from shapely.ops import unary_union


_engine: Engine | None = None


def _conn_url() -> str:
    host = os.getenv("STATIC_DB_HOST", "static-db")
    port = os.getenv("STATIC_DB_PORT", "5432")
    db = os.getenv("STATIC_DB_NAME", "nav_static")
    user = os.getenv("STATIC_DB_USER", "nav_static")
    pwd = os.getenv("STATIC_DB_PASSWORD", "nav_static")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_conn_url(), future=True)
    return _engine


def _to_wkt_union(polys) -> str:
    """
    Shapely Polygon/MultiPolygon のリストを 4326 の MultiPolygon WKT にまとめる。
    """
    if not polys:
        return "MULTIPOLYGON EMPTY"
    mp = unary_union(polys)
    # Shapely の WKT 出力（4326前提）
    return mp.wkt


def query_pois(polys) -> List[Dict]:
    """
    PostGIS の POI テーブルから、ポリゴン群に交差するスポットを取得。
    期待テーブル（最低限）：
      - pois(id, name, geom geometry(Point,4326), ...）
    本番ではスキーマに合わせて調整してください。
    DB 未接続の場合は空配列を返します（上位でモック/スタブ可）。
    """
    try:
        eng = _get_engine()
    except Exception:
        return []

    wkt = _to_wkt_union(polys)
    sql = text(
        """
        SELECT id::text AS spot_id,
               name,
               ST_X(geom)::float AS lon,
               ST_Y(geom)::float AS lat
        FROM pois
        WHERE ST_Intersects(
            geom,
            ST_GeomFromText(:wkt, 4326)
        )
        """
    )
    try:
        with eng.connect() as conn:
            rows = conn.execute(sql, {"wkt": wkt}).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        # スキーマ差異や未作成時などは空で返す
        return []
