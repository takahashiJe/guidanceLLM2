import os
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import create_engine, text, bindparam
from dataclasses import dataclass

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

@dataclass
class SpotInfo:
    """スポットの詳細情報を格納するデータクラス"""
    spot_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    md_slug: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

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
            WITH combined AS (
              SELECT sp.spot_id::text AS spot_id,
                     ST_X(sp.geom) AS lon,
                     ST_Y(sp.geom) AS lat,
                     1 AS ord
              FROM spots sp
              WHERE sp.spot_id IN :ids

              UNION ALL

              SELECT fc.spot_id::text AS spot_id,
                     ST_X(fc.geom) AS lon,
                     ST_Y(fc.geom) AS lat,
                     2 AS ord
              FROM facilities fc
              WHERE fc.spot_id IN :ids
            )
            SELECT DISTINCT ON (spot_id) spot_id, lon, lat
            FROM combined
            ORDER BY spot_id, ord;
        """).bindparams(bindparam("ids", expanding=True))

        out: Dict[str, Tuple[float, float]] = {}
        with _engine.begin() as conn:
            rows = conn.execute(sql, {"ids": ids}).mappings().all()
            for r in rows:
                out[r["spot_id"]] = (float(r["lon"]), float(r["lat"]))
        return out
    @staticmethod
    def get_spots_by_ids(ids: Iterable[str], lang: str) -> Dict[str, SpotInfo]:
        """
        【移植】指定されたIDのスポット情報を多言語で取得する。
        nav/spot_repo.py の get_spots_by_ids を移植・統合。
        """
        id_list = [str(i) for i in ids if i]
        if not id_list or lang not in ['ja', 'en', 'zh']:
            return {}

        sql = text(f"""
            WITH combined AS (
                SELECT
                    s.spot_id::text AS spot_id,
                    COALESCE(
                        s.official_name->>'{lang}',
                        s.official_name->>'ja',
                        s.official_name->>'en',
                        s.official_name->>'zh'
                    ) AS name,
                    COALESCE(
                        s.description->>'{lang}',
                        s.description->>'ja',
                        s.description->>'en',
                        s.description->>'zh'
                    ) AS description,
                    s.md_slug,
                    ST_Y(s.geom) AS lat,
                    ST_X(s.geom) AS lon,
                    1 AS ord
                FROM spots s
                WHERE s.spot_id IN :ids

                UNION ALL

                SELECT
                    f.spot_id::text AS spot_id,
                    COALESCE(
                        f.official_name->>'{lang}',
                        f.official_name->>'ja',
                        f.official_name->>'en',
                        f.official_name->>'zh'
                    ) AS name,
                    COALESCE(
                        f.description->>'{lang}',
                        f.description->>'ja',
                        f.description->>'en',
                        f.description->>'zh'
                    ) AS description,
                    f.md_slug,
                    ST_Y(f.geom) AS lat,
                    ST_X(f.geom) AS lon,
                    2 AS ord
                FROM facilities f
                WHERE f.spot_id IN :ids
            )
            SELECT DISTINCT ON (spot_id)
                spot_id,
                name,
                description,
                md_slug,
                lat,
                lon
            FROM combined
            ORDER BY spot_id, ord;
        """).bindparams(bindparam("ids", expanding=True))

        out: Dict[str, SpotInfo] = {}
        with _engine.begin() as conn:
            rows = conn.execute(sql, {"ids": id_list}).mappings().all()
            for r in rows:
                out[r["spot_id"]] = SpotInfo(
                    spot_id=r["spot_id"],
                    name=r.get("name"),
                    description=r.get("description"),
                    md_slug=r.get("md_slug"),
                    lat=r["lat"],
                    lon=r["lon"]
                )
        return out
    @staticmethod
    def resolve_one(spot_id: str) -> Optional[Tuple[float, float]]:
        m = SpotRepo.resolve_many([spot_id])
        return m.get(spot_id)
