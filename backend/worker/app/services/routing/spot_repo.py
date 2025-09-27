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
    def get_spots_by_ids(ids: Iterable[str], lang: str) -> Dict[str, SpotInfo]:
        """
        【移植】指定されたIDのスポット情報を多言語で取得する。
        nav/spot_repo.py の get_spots_by_ids を移植・統合。
        """
        id_list = [str(i) for i in ids if i]
        if not id_list or lang not in ['ja', 'en', 'zh']:
            return {}

        sql = text(f"""
            WITH all_pois AS (
                SELECT spot_id, official_name, description, md_slug, geom, 1 as tbl_ord
                FROM spots WHERE spot_id = ANY(:ids)
                UNION ALL
                SELECT spot_id, official_name, description, md_slug, geom, 2 as tbl_ord
                FROM facilities WHERE spot_id = ANY(:ids)
            )
            SELECT DISTINCT ON (spot_id)
                spot_id::text,
                official_name->>'{lang}' AS name,
                description->>'{lang}' AS description,
                md_slug,
                ST_Y(geom) AS lat,
                ST_X(geom) AS lon
            FROM all_pois
            ORDER BY spot_id, tbl_ord;
        """)

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
