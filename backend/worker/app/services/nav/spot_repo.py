from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from sqlalchemy import create_engine, text, bindparam
from sqlalchemy.engine import Engine, Result


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
    db = os.getenv("STATIC_DB_NAME", "nav_static")
    user = os.getenv("STATIC_DB_USER", "nav_static")
    pwd = os.getenv("STATIC_DB_PASSWORD", "nav_static")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_conn_url(), future=True)
    return _engine


def get_spots_by_ids(ids: Iterable[str]) -> Dict[str, SpotRow]:
    """
    spots テーブルから id 群を引き、 {spot_id: SpotRow} を返す。
    想定カラム: id (PK), name, description, md_slug
    """
    id_list = [str(i) for i in ids if i]
    if not id_list:
        return {}

    sql = text(
        """
        SELECT
          id::text AS spot_id,
          name,
          description,
          md_slug,
          lat,
          lon
        FROM spots
        WHERE id IN :ids
        """
    ).bindparams(bindparam("ids", expanding=True))

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
    except Exception:
        print(f"Error fetching spots: {e}")
        # DB 未起動などでも nav は動かしたいので、空で返す
        return {}
