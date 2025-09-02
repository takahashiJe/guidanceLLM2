import os
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import create_engine, text

# ─────────────────────────────────────────────────────────────
# DSN を ENV から構築（docker-compose で渡している変数を使用）
# ─────────────────────────────────────────────────────────────
_HOST = os.getenv("STATIC_DB_HOST", "static-db")
_NAME = os.getenv("STATIC_DB_NAME", "static_db")
_USER = os.getenv("STATIC_DB_USER", "static_db")
_PWD  = os.getenv("STATIC_DB_PASSWORD", "static_db")
_PORT = os.getenv("STATIC_DB_PORT", "5432")

# SQLAlchemy 2.x + psycopg
_DSN = f"postgresql+psycopg2://{_USER}:{_PWD}@{_HOST}:{_PORT}/{_NAME}"

_engine = create_engine(
    _DSN,
    pool_pre_ping=True,
    future=True,
)

class SpotRepo:
    """
    spot_id -> (lon, lat) を DB（spots / facilities）から解決する。
    - 両方に同一 spot_id が存在するケースは通常想定しないが、
      UNION ALL の順序上「spots が先勝ち」になるよう制御。
    """

    @staticmethod
    def resolve_many(spot_ids: Iterable[str]) -> Dict[str, Tuple[float, float]]:
        ids = [sid for sid in spot_ids if sid]
        if not ids:
            return {}

        # 1回のSQLで両テーブルを横断検索（SRID=4326 の POINT 前提）
        sql = text("""
            WITH target AS (
              SELECT unnest(:ids) AS spot_id
            ),
            s AS (
              SELECT t.spot_id, ST_X(sp.geom) AS lon, ST_Y(sp.geom) AS lat, 1 AS ord
              FROM target t
              JOIN spots sp ON sp.spot_id = t.spot_id
            ),
            f AS (
              SELECT t.spot_id, ST_X(fc.geom) AS lon, ST_Y(fc.geom) AS lat, 2 AS ord
              FROM target t
              JOIN facilities fc ON fc.spot_id = t.spot_id
            ),
            u AS (
              SELECT * FROM s
              UNION ALL
              SELECT * FROM f
            )
            SELECT DISTINCT ON (spot_id) spot_id, lon, lat
            FROM u
            ORDER BY spot_id, ord;
        """)

        out: Dict[str, Tuple[float, float]] = {}
        with _engine.begin() as conn:
            rows = conn.execute(sql, {"ids": ids}).mappings().all()
            for r in rows:
                out[r["spot_id"]] = (float(r["lon"]), float(r["lat"]))
        return out

    @staticmethod
    def resolve_one(spot_id: str) -> Optional[Tuple[float, float]]:
        m = SpotRepo.resolve_many([spot_id])
        return m.get(spot_id)
