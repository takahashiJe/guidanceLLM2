#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Static DB 初期化スクリプト（PostGIS 拡張・GIST インデックス・統合ビュー）
- PostGIS 拡張の有効化
- spots / facilities の geom に GIST インデックス（存在しなければ作成）
- 観光スポットと施設を統合する VIEW: poi_features_v を作成
- （任意）環境変数 LOAD_STATIC_JSON=1 の時のみ、POI.json / facilities.json を軽量投入
    * JSON スキーマ差異に耐えるよう best-effort で挿入（無理せずスキップ）
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection


# -------------------------
# DB 接続
# -------------------------
def _conn_url() -> str:
    host = os.getenv("STATIC_DB_HOST", "static-db")
    port = os.getenv("STATIC_DB_PORT", "5432")
    db   = os.getenv("STATIC_DB_NAME", "nav_static")
    user = os.getenv("STATIC_DB_USER", "nav_static")
    pwd  = os.getenv("STATIC_DB_PASSWORD", "nav_static")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


def _engine() -> Engine:
    return create_engine(_conn_url(), future=True)


# -------------------------
# DDL（拡張・インデックス・ビュー）
# -------------------------
DDL_CREATE_TABLE_SPOTS = """
CREATE TABLE IF NOT EXISTS spots (
    spot_id TEXT PRIMARY KEY,
    category TEXT NOT NULL DEFAULT 'tourist_spot',
    official_name JSONB NOT NULL,
    aliases JSONB,
    description JSONB,
    social_proof JSONB,
    tags JSONB,
    address JSONB,
    osm_place_id BIGINT,
    osm_type TEXT,
    osm_id BIGINT,
    md_slug TEXT,
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

DDL_CREATE_TABLE_FACILITIES = """
CREATE TABLE IF NOT EXISTS facilities (
    spot_id TEXT PRIMARY KEY,
    category TEXT NOT NULL DEFAULT 'accommodation',
    official_name JSONB NOT NULL,
    aliases JSONB,
    description JSONB,
    social_proof JSONB,
    tags JSONB,
    address JSONB,
    osm_place_id BIGINT,
    osm_type TEXT,
    osm_id BIGINT,
    md_slug TEXT,
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""
DDL_INDEX_ACCESS_POINTS = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'idx_access_points_geom' AND n.nspname = 'public'
    ) THEN
        EXECUTE 'CREATE INDEX idx_access_points_geom ON access_points USING GIST (geom)';
    END IF;
END$$;
"""

DDL_CREATE_TABLE_ACCESS_POINTS = """
CREATE TABLE IF NOT EXISTS access_points (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    osm_type TEXT,
    osm_id BIGINT,
    name TEXT,
    properties JSONB,
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

DDL_ENABLE_POSTGIS = """
CREATE EXTENSION IF NOT EXISTS postgis;
"""

DDL_INDEX_SPOTS = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'idx_spots_geom' AND n.nspname = 'public'
    ) THEN
        EXECUTE 'CREATE INDEX idx_spots_geom ON spots USING GIST (geom)';
    END IF;
END$$;
"""

DDL_INDEX_FACILITIES = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'idx_facilities_geom' AND n.nspname = 'public'
    ) THEN
        EXECUTE 'CREATE INDEX idx_facilities_geom ON facilities USING GIST (geom)';
    END IF;
END$$;
"""

DDL_VIEW_POI_FEATURES_V = """
CREATE OR REPLACE VIEW poi_features_v AS
SELECT
  s.spot_id::text AS spot_id,
  COALESCE(
    s.official_name->>'ja',
    s.official_name->>'en',
    s.official_name->>'zh',
    s.aliases->>'ja',
    s.aliases->>'en',
    s.aliases->>'zh',
    'unknown'
  ) AS name,
  ST_X(s.geom)::float AS lon,
  ST_Y(s.geom)::float AS lat,
  'spot'::text AS kind,
  s.geom
FROM spots s
UNION ALL
SELECT
  f.spot_id::text AS spot_id,
  COALESCE(
    f.official_name->>'ja',
    f.official_name->>'en',
    f.official_name->>'zh',
    f.aliases->>'ja',
    f.aliases->>'en',
    f.aliases->>'zh',
    'unknown'
  ) AS name,
  ST_X(f.geom)::float AS lon,
  ST_Y(f.geom)::float AS lat,
  'facility'::text AS kind,
  f.geom
FROM facilities f;
"""


def apply_ddl(conn: Connection) -> None:
    conn.execute(text(DDL_ENABLE_POSTGIS))
    conn.execute(text(DDL_CREATE_TABLE_SPOTS))
    conn.execute(text(DDL_CREATE_TABLE_FACILITIES))
    conn.execute(text(DDL_CREATE_TABLE_ACCESS_POINTS))
    conn.execute(text(DDL_INDEX_SPOTS))
    conn.execute(text(DDL_INDEX_FACILITIES))
    conn.execute(text(DDL_INDEX_ACCESS_POINTS))
    conn.execute(text(DDL_VIEW_POI_FEATURES_V))


# -------------------------
# 任意: JSON 投入（best-effort）
# -------------------------
def _read_json(path: Path) -> Optional[Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _to_jsonb_name(name_ja: Optional[str], name_en: Optional[str] = None, name_zh: Optional[str] = None) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if name_ja:
        out["ja"] = name_ja
    if name_en:
        out["en"] = name_en
    if name_zh:
        out["zh"] = name_zh
    return out


SQL_UPSERT_SPOT = text(
    """
    INSERT INTO spots (id, official_name, aliases, description, md_slug, geom)
    VALUES (:id, :official_name::jsonb, :aliases::jsonb, :description, :md_slug,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
    ON CONFLICT (id) DO UPDATE SET
        official_name = EXCLUDED.official_name,
        aliases       = EXCLUDED.aliases,
        description   = EXCLUDED.description,
        md_slug       = EXCLUDED.md_slug,
        geom          = EXCLUDED.geom
    """
)

SQL_UPSERT_FACILITY = text(
    """
    INSERT INTO facilities (id, official_name, aliases, description, md_slug, geom)
    VALUES (:id, :official_name::jsonb, :aliases::jsonb, :description, :md_slug,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
    ON CONFLICT (id) DO UPDATE SET
        official_name = EXCLUDED.official_name,
        aliases       = EXCLUDED.aliases,
        description   = EXCLUDED.description,
        md_slug       = EXCLUDED.md_slug,
        geom          = EXCLUDED.geom
    """
)


def _safe_id(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _coerce_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _guess_names(rec: Dict[str, Any]) -> Dict[str, Optional[str]]:
    # よくあるキー名に対応（存在しなければ None）
    return {
        "ja": rec.get("name_ja") or rec.get("ja") or rec.get("name") or rec.get("official_name_ja"),
        "en": rec.get("name_en") or rec.get("en") or rec.get("official_name_en"),
        "zh": rec.get("name_zh") or rec.get("zh") or rec.get("official_name_zh"),
    }


def _guess_aliases(rec: Dict[str, Any]) -> Dict[str, Any]:
    # シンプルに空の dict を既定。必要なら将来拡張。
    return {}


def _guess_md_slug(rec: Dict[str, Any]) -> Optional[str]:
    slug = rec.get("md_slug")
    if slug:
        return str(slug)
    # POI.json に slug が無い場合は None
    return None


def load_spots_from_poi_json(conn: Connection, poi_json_path: Path) -> None:
    data = _read_json(poi_json_path)
    if not isinstance(data, list):
        return

    for rec in data:
        # POI.json には施設も入っている可能性があるが、ここでは「基本 spot 扱い」
        sid = _safe_id(rec.get("id") or rec.get("spot_id"))
        lat = _coerce_float(rec.get("lat"))
        lon = _coerce_float(rec.get("lon"))
        if not (sid and lat is not None and lon is not None):
            continue

        names = _guess_names(rec)
        official_name = _to_jsonb_name(names["ja"], names["en"], names["zh"])
        aliases = _guess_aliases(rec)
        desc = rec.get("description") or rec.get("desc") or None
        md_slug = _guess_md_slug(rec)

        conn.execute(
            SQL_UPSERT_SPOT,
            {
                "id": sid,
                "official_name": json.dumps(official_name),
                "aliases": json.dumps(aliases),
                "description": desc,
                "md_slug": md_slug,
                "lat": lat,
                "lon": lon,
            },
        )


def load_facilities_from_json(conn: Connection, facilities_json_path: Path) -> None:
    data = _read_json(facilities_json_path)
    if not isinstance(data, list):
        return

    for rec in data:
        fid = _safe_id(rec.get("id") or rec.get("facility_id"))
        lat = _coerce_float(rec.get("lat"))
        lon = _coerce_float(rec.get("lon"))
        if not (fid and lat is not None and lon is not None):
            continue

        names = _guess_names(rec)
        official_name = _to_jsonb_name(names["ja"], names["en"], names["zh"])
        aliases = _guess_aliases(rec)
        desc = rec.get("description") or rec.get("desc") or None
        md_slug = _guess_md_slug(rec)

        conn.execute(
            SQL_UPSERT_FACILITY,
            {
                "id": fid,
                "official_name": json.dumps(official_name),
                "aliases": json.dumps(aliases),
                "description": desc,
                "md_slug": md_slug,
                "lat": lat,
                "lon": lon,
            },
        )


# -------------------------
# main
# -------------------------
def main() -> int:
    engine = _engine()
    with engine.begin() as conn:
        # DDL（拡張・インデックス・ビュー）
        apply_ddl(conn)

        # 任意: JSON 投入（必要時のみ）
        if os.getenv("LOAD_STATIC_JSON", "0") == "1":
            # 既定のファイルパス（存在すればロード）
            # プロジェクト構成に合わせて調整。相対/絶対どちらでも可。
            root = Path(__file__).resolve().parents[2]  # backend/
            default_poi = root / "worker" / "data" / "POI.json"
            default_fac = root / "worker" / "data" / "facilities.json"

            poi_path = Path(os.getenv("POI_JSON_PATH", str(default_poi)))
            fac_path = Path(os.getenv("FACILITIES_JSON_PATH", str(default_fac)))

            if poi_path.exists():
                load_spots_from_poi_json(conn, poi_path)
            if fac_path.exists():
                load_facilities_from_json(conn, fac_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
