from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@dataclass
class AccessPoint:
    lat: float
    lon: float
    id: Optional[int] = None
    name: Optional[str] = None


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


def get_nearest_access_point(dest_lat: float, dest_lon: float) -> Optional[AccessPoint]:
    """
    PostGIS の access_points テーブルから最寄りを 1 件返す。
    テーブル定義の想定（最低限）:
      - id (pk)
      - name (optional)
      - geom geometry(Point, 4326)
    ※ 実際のカラム名が異なる場合はこのクエリを調整してください。
    """
    sql = text(
        """
        SELECT id, name,
               ST_Y(geom)::float AS lat,
               ST_X(geom)::float AS lon
        FROM access_points
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        LIMIT 1
        """
    )
    try:
        eng = _get_engine()
        with eng.connect() as conn:
            row = conn.execute(sql, {"lat": dest_lat, "lon": dest_lon}).first()
            if not row:
                return None
            return AccessPoint(lat=row.lat, lon=row.lon, id=row.id, name=row.name)
    except Exception:
        # DB 未起動などの場合は None を返す（上位でフォールバック）
        return None
