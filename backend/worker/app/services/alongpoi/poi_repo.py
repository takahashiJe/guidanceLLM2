from __future__ import annotations

import os
from typing import List, Dict, Iterable
import json

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon, MultiLineString, mapping
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid
import logging

# print文が見つけやすいように、目立つセパレータを使います
SEPARATOR = "■■■ DEBUG ■■■"
log = logging.getLogger(__name__)
_engine: Engine | None = None

def _clean_and_extract_polygons(geoms: Iterable[BaseGeometry]) -> List[Polygon]:
    cleaned_polygons: List[Polygon] = []
    # print文はロガー設定の影響を受けないため、確実に出力されます
    print(f"{SEPARATOR} Starting cleaning for {len(list(geoms))} geometries.", flush=True)

    for i, g in enumerate(geoms):
        if not isinstance(g, BaseGeometry) or g.is_empty:
            print(f"{SEPARATOR} [Geom {i}] Skipping invalid or empty geometry. Type: {type(g)}", flush=True)
            continue

        print(f"{SEPARATOR} [Geom {i}] Processing geometry. Original valid: {g.is_valid}, Type: {g.geom_type}", flush=True)
        geom_to_process = make_valid(g) if not g.is_valid else g

        if geom_to_process.geom_type == 'Polygon':
            cleaned_polygons.append(geom_to_process)
            print(f"{SEPARATOR}    -> Extracted a valid Polygon.", flush=True)
        elif geom_to_process.geom_type == 'MultiPolygon':
            extracted = list(geom_to_process.geoms)
            cleaned_polygons.extend(extracted)
            print(f"{SEPARATOR}    -> Extracted {len(extracted)} Polygons from a MultiPolygon.", flush=True)
        elif geom_to_process.geom_type == 'GeometryCollection':
            print(f"{SEPARATOR}    -> Handling GeometryCollection...", flush=True)
            initial_count = len(cleaned_polygons)
            for geom in geom_to_process.geoms:
                if geom.geom_type == 'Polygon':
                    cleaned_polygons.append(geom)
                elif geom.geom_type == 'MultiPolygon':
                    cleaned_polygons.extend(list(geom.geoms))
            print(f"{SEPARATOR}      -> Extracted {len(cleaned_polygons) - initial_count} Polygons from GeometryCollection.", flush=True)
    
    print(f"{SEPARATOR} Cleaning finished. {len(cleaned_polygons)} valid polygons extracted.", flush=True)
    return cleaned_polygons


def _conn_url() -> str:
    host = os.getenv("STATIC_DB_HOST", "static-db")
    port = os.getenv("STATIC_DB_PORT", "5432")
    db   = os.getenv("STATIC_DB_NAME", "nav_static")
    user = os.getenv("STATIC_DB_USER", "nav_static")
    pwd  = os.getenv("STATIC_DB_PASSWORD", "nav_static")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_conn_url(), future=True)
    return _engine

def _build_geometry_collection_wkt(polys: List[BaseGeometry]) -> str | None:
    """
    ポリゴンのリストを GEOMETRYCOLLECTION の WKT 文字列に変換する。
    これにより unary_union を完全に回避する。
    """
    valid_polygons = _clean_and_extract_polygons(polys)
    if not valid_polygons:
        log.warning("No valid polygons found after cleaning.")
        return None
    
    # 各ポリゴンのWKT表現を抽出し、カンマで連結
    wkt_bodies = ", ".join(p.wkt for p in valid_polygons)
    return f"GEOMETRYCOLLECTION({wkt_bodies})"

def _union_wkt(polys: List[BaseGeometry]) -> str | None:
    valid_polygons = _clean_and_extract_polygons(polys)
    # 1. ポリゴンがリストにない場合は、Noneを返す
    if not valid_polygons:
        log.warning("No valid polygons found after cleaning. Skipping POI query.")
        print(f"{SEPARATOR} No valid polygons found after cleaning. Skipping POI query.", flush=True)
        return None

    # 2. ポリゴンが1つだけの場合は、結合処理をスキップしてそのままWKTを返す
    if len(valid_polygons) == 1:
        log.info("Only one valid polygon found. Skipping unary_union and returning its WKT directly.")
        return valid_polygons[0].wkt

    # 3. ポリゴンが複数ある場合のみ、結合処理を実行する
    log.info(f"Multiple ({len(valid_polygons)}) valid polygons found. Proceeding with unary_union.")
    unioned_geom = unary_union(valid_polygons)
    return unioned_geom.wkt

    print(f"{SEPARATOR} Preparing to union {len(valid_polygons)} polygons. Inspecting list contents:", flush=True)
    all_polygons_valid = True
    for i, p in enumerate(valid_polygons):
        is_poly = isinstance(p, Polygon)
        # ここで型と有効性を強制的に出力します
        print(f"{SEPARATOR}  [Poly {i}] Type: {type(p)}, Is Polygon: {is_poly}, Is Valid: {p.is_valid}", flush=True)
        if not is_poly:
            all_polygons_valid = False
            print(f"{SEPARATOR}   !!!! CRITICAL: Item at index {i} is NOT a Polygon.", flush=True)

    if not all_polygons_valid:
        print(f"{SEPARATOR} Aborting union due to non-polygon objects.", flush=True)
        # エラーを発生させて処理を停止
        raise TypeError("Attempted to union a list containing non-polygon objects.")
    
    print(f"{SEPARATOR} All checks passed. Calling unary_union...", flush=True)
    unioned_geom = unary_union(valid_polygons)
    print(f"{SEPARATOR} unary_union call successful.", flush=True)
    return unioned_geom.wkt


_SQL_QUERY = text(
    """
    SELECT spot_id, name, lon, lat, kind
    FROM poi_features_v
    WHERE ST_Intersects(
        geom,
        ST_GeomFromText(:wkt, 4326)
    )
    """
)


def query_pois(polys: List[BaseGeometry]) -> List[Dict]:
    wkt = _build_geometry_collection_wkt(polys)
    if not wkt:
        return []
    try:
        eng = _get_engine()
    except Exception:
        return []

    try:
        with eng.connect() as conn:
            rows = conn.execute(_SQL_QUERY, {"wkt": wkt}).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        return []

_SQL_NEARBY = text("""
WITH car_line AS (
  SELECT CASE WHEN :car_geojson IS NOT NULL
              THEN ST_GeomFromGeoJSON(:car_geojson)::geometry END AS g
),
foot_line AS (
  SELECT CASE WHEN :foot_geojson IS NOT NULL
              THEN ST_GeomFromGeoJSON(:foot_geojson)::geometry END AS g
),
car_geog  AS (SELECT CASE WHEN g IS NOT NULL THEN g::geography END AS gg FROM car_line),
foot_geog AS (SELECT CASE WHEN g IS NOT NULL THEN g::geography END AS gg FROM foot_line)
SELECT
  p.spot_id, p.name, p.lon, p.lat, p.kind,
  LEAST(
    COALESCE(ST_Distance(p.geom::geography, (SELECT gg FROM car_geog)),  1e15),
    COALESCE(ST_Distance(p.geom::geography, (SELECT gg FROM foot_geog)), 1e15)
  ) AS distance_m,
  CASE
    WHEN (SELECT gg FROM car_geog)  IS NOT NULL
     AND ST_DWithin(p.geom::geography, (SELECT gg FROM car_geog),  :car_m)  THEN 'car'
    WHEN (SELECT gg FROM foot_geog) IS NOT NULL
     AND ST_DWithin(p.geom::geography, (SELECT gg FROM foot_geog), :foot_m) THEN 'foot'
    ELSE NULL
  END AS source_segment_mode
FROM poi_features_v p
WHERE
  ( (SELECT gg FROM car_geog)  IS NOT NULL AND ST_DWithin(p.geom::geography, (SELECT gg FROM car_geog),  :car_m) )
  OR
  ( (SELECT gg FROM foot_geog) IS NOT NULL AND ST_DWithin(p.geom::geography, (SELECT gg FROM foot_geog), :foot_m) )
""")

def _to_geojson_or_none(mls: MultiLineString | None) -> str | None:
    if mls is None:
        return None
    return json.dumps(mapping(mls), ensure_ascii=False)

def query_pois_near_route(
    lines: dict,  # {"car": MultiLineString|None, "foot": MultiLineString|None}
    car_m: float,
    foot_m: float,
) -> List[Dict]:
    try:
        eng = _get_engine()
    except Exception:
        return []

    params = {
        "car_geojson":  _to_geojson_or_none(lines.get("car")),
        "foot_geojson": _to_geojson_or_none(lines.get("foot")),
        "car_m": float(car_m),
        "foot_m": float(foot_m),
    }

    try:
        with eng.connect() as conn:
            rows = conn.execute(_SQL_NEARBY, params).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        return []
