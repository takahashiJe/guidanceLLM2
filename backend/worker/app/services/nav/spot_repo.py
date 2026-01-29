from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from sqlalchemy import create_engine, text, bindparam
from sqlalchemy.engine import Engine, Result
import json


@dataclass
class SpotRow:
    spot_id: str
    name: Optional[str]
    description: Optional[str]
    md_slug: Optional[str]
    lat: Optional[float] = None
    lon: Optional[float] = None


_engine: Engine | None = None


def _conn_url() -> str:
    host = os.getenv("STATIC_DB_HOST", "static-db")
    port = os.getenv("STATIC_DB_PORT", "5432")
    db = os.getenv("STATIC_DB_NAME", "static-db")
    user = os.getenv("STATIC_DB_USER", "static-db")
    pwd = os.getenv("STATIC_DB_PASSWORD", "static-db")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_conn_url(), future=True)
    return _engine


def get_spots_by_ids(ids: Iterable[str], lang: str) -> Dict[str, SpotRow]:
    """
    spots テーブルから spot_id 群を引き、 {spot_id: SpotRow} を返す。
    想定カラム: spot_id (PK), name, description, md_slug
    """
    id_list = [str(i) for i in ids if i]
    if not id_list:
        return {}
    
    if lang not in ['ja', 'en', 'zh']:
        return {}
    
    sql_query = f"""
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
        ORDER BY spot_id, ord
    """
    sql = text(sql_query).bindparams(bindparam("ids", expanding=True))

    try:
        eng = _get_engine()
        with eng.connect() as conn:
            rows: Result = conn.execute(sql, {"ids": id_list})
            out: Dict[str, SpotRow] = {}
            for r in rows.mappings():
                out[r["spot_id"]] = SpotRow(
                    spot_id=r["spot_id"],
                    name=r.get("name"),
                    description=r.get("description"),
                    md_slug=r.get("md_slug"),
                    lat=r["lat"],
                    lon=r["lon"]
                )
            return out
    except Exception as e:
        print(f"Error fetching spots: {e}")
        # DB 未起動などでも nav は動かしたいので、空で返す
        return {}
