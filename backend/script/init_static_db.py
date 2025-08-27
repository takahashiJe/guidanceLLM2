import os
import sys
import json
import orjson
from pathlib import Path

from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker

# GeoAlchemy2
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

# あなたのモデル（Spot / Facility）は shared.models にある前提
# Spot / Facility のクラス名は添付 models.py に合わせてください
try:
    from shared.models import Base, Spot, Facility  # Baseはdeclarative_base()
except Exception as e:
    print("[FATAL] models import failed:", e, file=sys.stderr)
    sys.exit(1)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "nav_static")
DB_USER = os.getenv("DB_USER", "nav_static")
DB_PASSWORD = os.getenv("DB_PASSWORD", "nav_static")

POI_JSON = Path(os.getenv("POI_JSON", "/app/backend/worker/data/POI.json"))
FACILITIES_JSON = Path(os.getenv("FACILITIES_JSON", "/app/backend/worker/data/facilities.json"))
ACCESS_POINTS = Path(os.getenv("ACCESS_POINTS", "/app/backend/worker/data/access_points.geojson"))
FORCE_INSERT = os.getenv("FORCE_INSERT", "0") == "1"

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, future=True)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def load_json(path: Path):
    with path.open("rb") as f:
        try:
            return orjson.loads(f.read())
        except Exception:
            f.seek(0)
            return json.load(f)

def normalize_md_slug(v):
    if v is None:
        return None
    if isinstance(v, str) and v.strip().lower() in {"none", ""}:
        return None
    return v.strip()

def ensure_postgis(conn):
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

def create_indices(conn):
    # GIST
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_spots_geom_gist ON spots USING GIST (geom)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_facilities_geom_gist ON facilities USING GIST (geom)"))
    # JSONB GIN（存在する場合のみ作成を試行）
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_spots_official_name_gin ON spots USING GIN (official_name)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_spots_aliases_gin ON spots USING GIN (aliases)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_spots_tags_gin ON spots USING GIN (tags)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_facilities_official_name_gin ON facilities USING GIN (official_name)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_facilities_aliases_gin ON facilities USING GIN (aliases)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_facilities_tags_gin ON facilities USING GIN (tags)"))
    # access_points 用（後述でテーブル作成）
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_access_points_geom_gist ON access_points USING GIST (geom)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_access_points_props_gin ON access_points USING GIN (properties)"))

def ensure_access_points_table(conn):
    # テーブルが無ければ作成（単純な汎用スキーマ）
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS access_points (
          id TEXT PRIMARY KEY,
          properties JSONB,
          geom geometry(Point, 4326) NOT NULL
        )
    """))

def table_count(sess, model):
    return sess.scalar(select(text("count(1)")).select_from(model.__table__))

def insert_spots(sess, items):
    if not items:
        return 0
    inserted = 0
    for it in items:
        # JSONキーに合わせて取得（存在しないキーは None）
        spot_id = it.get("spot_id") or it.get("id")  # 柔軟に
        coords = (it.get("coordinates") or {})
        lon = coords.get("longitude") or coords.get("lon")
        lat = coords.get("latitude") or coords.get("lat")
        if spot_id is None or lon is None or lat is None:
            continue

        md_slug = normalize_md_slug(it.get("md_slug"))

        geom = from_shape(Point(float(lon), float(lat)), srid=4326)
        row = Spot(
            spot_id=spot_id,
            category=it.get("category") or "tourist_spot",
            official_name=it.get("official_name"),
            aliases=it.get("aliases"),
            description=it.get("description"),
            social_proof=it.get("social_proof"),
            tags=it.get("tags"),
            address=it.get("address"),
            osm_place_id=((it.get("osm_ids") or {}).get("place_id")),
            osm_type=((it.get("osm_ids") or {}).get("osm_type")),
            osm_id=((it.get("osm_ids") or {}).get("osm_id")),
            md_slug=md_slug,
            geom=geom,
        )
        # 既存があればスキップ（簡易）
        if sess.get(Spot, spot_id) is None:
            sess.add(row)
            inserted += 1
    return inserted

def insert_facilities(sess, items):
    if not items:
        return 0
    inserted = 0
    for it in items:
        spot_id = it.get("spot_id") or it.get("id")
        coords = (it.get("coordinates") or {})
        lon = coords.get("longitude") or coords.get("lon")
        lat = coords.get("latitude") or coords.get("lat")
        if spot_id is None or lon is None or lat is None:
            continue

        md_slug = normalize_md_slug(it.get("md_slug"))

        geom = from_shape(Point(float(lon), float(lat)), srid=4326)
        row = Facility(
            spot_id=spot_id,
            category=it.get("category") or "accommodation",
            official_name=it.get("official_name"),
            aliases=it.get("aliases"),
            description=it.get("description"),
            social_proof=it.get("social_proof"),
            tags=it.get("tags"),
            address=it.get("address"),
            osm_place_id=((it.get("osm_ids") or {}).get("place_id")),
            osm_type=((it.get("osm_ids") or {}).get("osm_type")),
            osm_id=((it.get("osm_ids") or {}).get("osm_id")),
            md_slug=md_slug,
            geom=geom,
        )
        if sess.get(Facility, spot_id) is None:
            sess.add(row)
            inserted += 1
    return inserted

def insert_access_points(sess, features):
    if not features:
        return 0
    # 生SQLでINSERT（単純に upsert は省略：id重複は無視）
    inserted = 0
    for feat in features:
        # GeoJSON 構造を想定
        gid = str(feat.get("id") or feat.get("properties", {}).get("id") or inserted+1)
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        if (geom.get("type") != "Point") or (not geom.get("coordinates")):
            continue
        lon, lat = geom["coordinates"][:2]
        # 存在チェック
        exists = sess.execute(text("SELECT 1 FROM access_points WHERE id = :id"), {"id": gid}).first()
        if exists:
            continue
        sess.execute(
            text("INSERT INTO access_points (id, properties, geom) VALUES (:id, :props, ST_SetSRID(ST_MakePoint(:lon,:lat),4326))"),
            {"id": gid, "props": json.dumps(props, ensure_ascii=False), "lon": float(lon), "lat": float(lat)}
        )
        inserted += 1
    return inserted

def main():
    print("[INFO] Connecting:", DATABASE_URL.replace(DB_PASSWORD, "****"))
    with engine.begin() as conn:
        ensure_postgis(conn)
        # Spot/Facility テーブルの作成
        Base.metadata.create_all(conn)
        # access_points テーブル
        ensure_access_points_table(conn)
        # 推奨インデックス
        create_indices(conn)

    sess = Session()
    try:
        # 既存データの有無
        spots_count = table_count(sess, Spot)
        facs_count = table_count(sess, Facility)

        # JSON 読み込み
        poi_items = load_json(POI_JSON) if POI_JSON.exists() else []
        fac_items = load_json(FACILITIES_JSON) if FACILITIES_JSON.exists() else []
        ap_geojson = load_json(ACCESS_POINTS) if ACCESS_POINTS.exists() else {}
        ap_features = ap_geojson.get("features") if isinstance(ap_geojson, dict) else []

        inserted_spots = inserted_facs = inserted_ap = 0

        if FORCE_INSERT or spots_count == 0:
            inserted_spots = insert_spots(sess, poi_items)
        else:
            print(f"[INFO] spots already has {spots_count} rows. Skip insert (set FORCE_INSERT=1 to force).")

        if FORCE_INSERT or facs_count == 0:
            inserted_facs = insert_facilities(sess, fac_items)
        else:
            print(f"[INFO] facilities already has {facs_count} rows. Skip insert (set FORCE_INSERT=1 to force).")

        if ap_features:
            inserted_ap = insert_access_points(sess, ap_features)

        sess.commit()
        print(f"[DONE] inserted: spots={inserted_spots}, facilities={inserted_facs}, access_points={inserted_ap}")

    except Exception as e:
        sess.rollback()
        print("[ERROR]", e, file=sys.stderr)
        raise
    finally:
        sess.close()

if __name__ == "__main__":
    main()
