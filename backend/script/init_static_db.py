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
import geojson
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
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_access_points_osm UNIQUE (osm_type, osm_id)
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
    INSERT INTO spots (spot_id, official_name, aliases, description, md_slug, geom)
    VALUES (:spot_id, CAST(:official_name AS jsonb), CAST(:aliases AS jsonb), :description, :md_slug,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
    ON CONFLICT (spot_id) DO UPDATE SET
        official_name = EXCLUDED.official_name,
        aliases       = EXCLUDED.aliases,
        description   = EXCLUDED.description,
        md_slug       = EXCLUDED.md_slug,
        geom          = EXCLUDED.geom
    """
)

SQL_UPSERT_FACILITY = text(
    """
    INSERT INTO facilities (spot_id, official_name, aliases, description, md_slug, geom)
    VALUES (:spot_id, CAST(:official_name AS jsonb), CAST(:aliases AS jsonb), :description, :md_slug,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
    ON CONFLICT (spot_id) DO UPDATE SET
        official_name = EXCLUDED.official_name,
        aliases       = EXCLUDED.aliases,
        description   = EXCLUDED.description,
        md_slug       = EXCLUDED.md_slug,
        geom          = EXCLUDED.geom
    """
)

SQL_UPSERT_ACCESS_POINT = """
INSERT INTO access_points (osm_type, osm_id, name, properties, geom)
VALUES (:osm_type, :osm_id, :name, :properties, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
ON CONFLICT (osm_type, osm_id) DO UPDATE SET
    name = EXCLUDED.name,
    properties = EXCLUDED.properties,
    geom = EXCLUDED.geom,
    updated_at = NOW();
"""

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
    official_name = rec.get("official_name", {}) or {}
    return {
        "ja": official_name.get("ja") or rec.get("name_ja") or rec.get("ja") or rec.get("name"),
        "en": official_name.get("en") or rec.get("name_en") or rec.get("en"),
        "zh": official_name.get("zh") or rec.get("name_zh") or rec.get("zh"),
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

    count = 0 # ★追加
    for rec in data:
        # POI.json には施設も入っている可能性があるが、ここでは「基本 spot 扱い」
        sid = _safe_id(rec.get("id") or rec.get("spot_id"))
        coords = rec.get("coordinates", {})
        lat = _coerce_float(coords.get("latitude"))
        lon = _coerce_float(coords.get("longitude"))
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
                "spot_id": sid,
                "official_name": json.dumps(official_name),
                "aliases": json.dumps(aliases),
                "description": json.dumps(desc, ensure_ascii=False),
                "md_slug": md_slug,
                "lat": lat,
                "lon": lon,
            },
        )
        count += 1 # ★追加
    print(f"  -> Upserted {count} spot records.") # ★追加


def load_facilities_from_json(conn: Connection, facilities_json_path: Path) -> None:
    data = _read_json(facilities_json_path)
    if not isinstance(data, list):
        return

    count = 0 # ★追加
    for rec in data:
        fid = _safe_id(rec.get("id") or rec.get("spot_id"))
        coords = rec.get("coordinates", {})
        lat = _coerce_float(coords.get("latitude"))
        lon = _coerce_float(coords.get("longitude"))
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
                "spot_id": fid,
                "official_name": json.dumps(official_name),
                "aliases": json.dumps(aliases),
                "description": json.dumps(desc, ensure_ascii=False) if desc else None,
                "md_slug": md_slug,
                "lat": lat,
                "lon": lon,
            },
        )
        count += 1 # ★追加
    print(f"  -> Upserted {count} facility records.") # ★追加

def load_access_points_from_geojson(conn: Connection, path: Path) -> None:
    """
    access_points.geojson を読み込み、access_points テーブルに UPSERT する。
    """
    print(f"Loading access points from: {path}")
    if not path.exists():
        print(f"  -> File not found. Skipping.")
        return

    with path.open("r") as f:
        data = geojson.load(f)

    count = 0
    for feature in data["features"]:
        try:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})

            # ジオメトリタイプがPointでなければスキップ
            if geom.get("type") != "Point":
                continue
            
            coords = geom.get("coordinates")
            if not coords or len(coords) < 2:
                continue
            lon, lat = coords[0], coords[1]

            # OSM IDのパース
            osm_full_id = props.get("@id", "")
            osm_type, osm_id_str = osm_full_id.split("/") if "/" in osm_full_id else (None, None)
            osm_id = int(osm_id_str) if osm_id_str and osm_id_str.isdigit() else None
            
            if not osm_type or osm_id is None:
                continue

            name = props.get("name")
            
            conn.execute(
                text(SQL_UPSERT_ACCESS_POINT),
                {
                    "osm_type": osm_type,
                    "osm_id": osm_id,
                    "name": name,
                    "properties": json.dumps(props),
                    "lon": lon,
                    "lat": lat,
                },
            )
            count += 1

        except Exception as e:
            # 1レコードのエラーで全体を止めない
            print(f"  -> Skipping a record due to error: {e}")
            continue
            
    print(f"  -> Upserted {count} records.")


# -------------------------
# main
# -------------------------
def main() -> int:
    print("--- Starting DB initialization script ---") # ★追加
    engine = _engine()
    try:
        with engine.begin() as conn:
            print("--- DB connection successful. Applying DDL... ---") # ★追加
            # DDL（拡張・インデックス・ビュー）
            apply_ddl(conn)
            print("--- DDL application finished. ---") # ★追加

            load_json_env = os.getenv("LOAD_STATIC_JSON", "0")
            print(f"--- Checking LOAD_STATIC_JSON flag: {load_json_env} ---") # ★追加

            # 任意: JSON 投入（必要時のみ）
            if load_json_env == "1":
                # 既定のファイルパス（存在すればロード）
                # プロジェクト構成に合わせて調整。相対/絶対どちらでも可。
                root = Path(__file__).resolve().parents[2]  # backend/
                default_poi = root / "worker" / "data" / "POI.json"
                default_fac = root / "worker" / "data" / "facilities.json"
                default_ap = root / "worker" / "data" / "access_points.geojson"

                poi_path = Path(os.getenv("POI_JSON_PATH"))
                fac_path = Path(os.getenv("FACILITIES_JSON_PATH", str(default_fac)))
                ap_path = Path(os.getenv("ACCESS_POINTS_PATH", str(default_ap)))

                print(f"POI file path: {poi_path}") # ★追加
                print(f"Facilities file path: {fac_path}") # ★追加
                print(f"Access points file path: {ap_path}") # ★追加

                if poi_path.exists():
                    load_spots_from_poi_json(conn, poi_path)
                else:
                    print(f"File not found: {poi_path}") # ★追加
                if fac_path.exists():
                    load_facilities_from_json(conn, fac_path)
                else:
                    print(f"File not found: {fac_path}") # ★追加
                if ap_path.exists():
                    load_access_points_from_geojson(conn, ap_path)
                else:
                    print(f"File not found: {ap_path}") # ★追加
            else:
                print("--- Skipping data loading because LOAD_STATIC_JSON is not '1'. ---") # ★追加
        print("--- DB initialization script finished successfully. ---") # ★追加
        return 0
    except Exception as e: # ★追加: エラーを明示的に出力
        print(f"!!! AN ERROR OCCURRED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
