from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pyproj import Transformer
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from shapely.geometry import (MultiLineString, MultiPolygon, Point, Polygon, shape)
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union
from shapely.validation import make_valid

# print文が見つけやすいように、目立つセパレータを使います
SEPARATOR = "■■■ DEBUG ■■■"
log = logging.getLogger(__name__)
_engine: Engine | None = None

_DEFAULT_FACILITIES_PATH = Path(__file__).resolve().parents[3] / "data" / "facilities.json"
_FACILITIES_PATH = Path(os.getenv("FACILITIES_JSON_PATH", str(_DEFAULT_FACILITIES_PATH)))
_TRANSFORMER_TO_3857 = Transformer.from_crs(4326, 3857, always_xy=True)

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

def _normalize_md_slug(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    slug = value.strip()
    if not slug or slug.lower() == "none":
        return None
    return slug


def _select_facility_name(rec: Dict[str, Any]) -> Optional[str]:
    official = rec.get("official_name") or {}
    for lang in ("ja", "en", "zh"):
        name = official.get(lang)
        if name:
            return str(name)
    aliases = rec.get("aliases") or {}
    for lang in ("ja", "en", "zh"):
        alias = aliases.get(lang)
        if isinstance(alias, list) and alias:
            return str(alias[0])
        if isinstance(alias, str) and alias:
            return str(alias)
    return None


def _iter_polygons(geom: BaseGeometry) -> Iterable[Polygon]:
    if geom.geom_type == "Polygon":
        yield geom
    elif geom.geom_type == "MultiPolygon":
        for sub in geom.geoms:
            if isinstance(sub, BaseGeometry) and not sub.is_empty:
                yield from _iter_polygons(sub)
    elif geom.geom_type == "GeometryCollection":
        for sub in geom.geoms:
            if isinstance(sub, BaseGeometry) and not sub.is_empty:
                yield from _iter_polygons(sub)


def _normalize_polygons(polys: Iterable[BaseGeometry]) -> List[Polygon]:
    normalized: List[Polygon] = []
    for geom in polys or []:
        if not isinstance(geom, BaseGeometry) or geom.is_empty:
            continue
        candidate = make_valid(geom) if not geom.is_valid else geom
        for poly in _iter_polygons(candidate):
            normalized.append(poly)
    return normalized


def _project_to_3857(geom: BaseGeometry) -> BaseGeometry:
    return transform(_TRANSFORMER_TO_3857.transform, geom)


@lru_cache(maxsize=1)
def _load_facility_records() -> List[Dict[str, Any]]:
    path = _FACILITIES_PATH
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for rec in data:
        spot_id = rec.get("spot_id") or rec.get("id")
        if not spot_id:
            continue
        sid = str(spot_id)
        if sid in seen:
            continue
        coords = rec.get("coordinates") or {}
        try:
            lat = float(coords.get("latitude"))
            lon = float(coords.get("longitude"))
        except (TypeError, ValueError):
            continue
        point = Point(lon, lat)
        record = {
            "spot_id": sid,
            "name": _select_facility_name(rec) or sid,
            "lon": lon,
            "lat": lat,
            "kind": "facility",
            "md_slug": _normalize_md_slug(rec.get("md_slug")),
            "geom": point,
            "geom_m": _project_to_3857(point),
        }
        records.append(record)
        seen.add(sid)
    return records


def _shape_to_3857(geojson_obj: Any) -> Optional[BaseGeometry]:
    if not geojson_obj:
        return None
    try:
        geom = shape(geojson_obj)
    except Exception:
        return None
    if geom.is_empty:
        return None
    return _project_to_3857(geom)


def _merge_hits(primary: List[Dict[str, Any]], extras: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not primary:
        return list(extras) if extras else []
    if not extras:
        return list(primary)

    merged = list(primary)
    seen = {hit.get("spot_id") for hit in merged if hit.get("spot_id")}
    for hit in extras:
        sid = hit.get("spot_id")
        if sid and sid in seen:
            continue
        merged.append(hit)
        if sid:
            seen.add(sid)
    return merged


def _query_facilities_in_polys(polys: Iterable[BaseGeometry]) -> List[Dict[str, Any]]:
    records = _load_facility_records()
    if not records:
        return []
    normalized = _normalize_polygons(polys)
    if not normalized:
        return []

    hits: List[Dict[str, Any]] = []
    for rec in records:
        pt: BaseGeometry = rec["geom"]
        if any(poly.intersects(pt) for poly in normalized):
            hits.append({
                "spot_id": rec["spot_id"],
                "name": rec["name"],
                "lon": rec["lon"],
                "lat": rec["lat"],
                "kind": rec["kind"],
                "md_slug": rec["md_slug"],
            })
    return hits


def _query_facilities_near_lines(
    lines: Optional[Dict[str, Any]],
    car_m: float,
    foot_m: float,
) -> List[Dict[str, Any]]:
    records = _load_facility_records()
    if not records:
        return []

    car_geom = _shape_to_3857((lines or {}).get("car"))
    foot_geom = _shape_to_3857((lines or {}).get("foot"))
    if car_geom is None and foot_geom is None:
        return []

    hits: List[Dict[str, Any]] = []
    for rec in records:
        distances: List[tuple[str, float]] = []
        if car_geom is not None:
            dist_car = float(car_geom.distance(rec["geom_m"]))
            if dist_car <= car_m:
                distances.append(("car", dist_car))
        if foot_geom is not None:
            dist_foot = float(foot_geom.distance(rec["geom_m"]))
            if dist_foot <= foot_m:
                distances.append(("foot", dist_foot))
        if not distances:
            continue

        mode, dist = min(distances, key=lambda item: item[1])
        hits.append({
            "spot_id": rec["spot_id"],
            "name": rec["name"],
            "lon": rec["lon"],
            "lat": rec["lat"],
            "kind": rec["kind"],
            "md_slug": rec["md_slug"],
            "distance_m": float(dist),
            "source_segment_mode": mode,
        })
    return hits

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
    facility_hits = _query_facilities_in_polys(polys)
    wkt = _build_geometry_collection_wkt(polys)

    db_hits: List[Dict[str, Any]] = []
    if wkt:
        try:
            eng = _get_engine()
            with eng.connect() as conn:
                rows = conn.execute(_SQL_QUERY, {"wkt": wkt}).mappings().all()
                db_hits = [dict(r) for r in rows]
        except Exception:
            db_hits = []

    return _merge_hits(db_hits, facility_hits)

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

def _to_geojson_or_none(geom: Any) -> str | None:
    if geom is None:
        return None
    # すでにGeoJSON辞書ならそのままdump
    if isinstance(geom, dict) and "type" in geom and "coordinates" in geom:
        return json.dumps(geom, ensure_ascii=False)
    # 念のためShapelyも許容（将来の流用に備え）
    try:
        from shapely.geometry import mapping as shp_mapping
        return json.dumps(shp_mapping(geom), ensure_ascii=False)
    except Exception:
        # 最後の砦：想定外の型はNone扱いにして落とさない
        return None

def query_pois_near_route(
    lines: dict,  # {"car": MultiLineString|None, "foot": MultiLineString|None}
    car_m: float,
    foot_m: float,
) -> List[Dict]:
    car_radius = float(car_m)
    foot_radius = float(foot_m)

    facility_hits = _query_facilities_near_lines(lines, car_radius, foot_radius)

    params = {
        "car_geojson": _to_geojson_or_none((lines or {}).get("car")),
        "foot_geojson": _to_geojson_or_none((lines or {}).get("foot")),
        "car_m": car_radius,
        "foot_m": foot_radius,
    }

    db_hits: List[Dict[str, Any]] = []
    try:
        eng = _get_engine()
        with eng.connect() as conn:
            rows = conn.execute(_SQL_NEARBY, params).mappings().all()
            db_hits = [dict(r) for r in rows]
    except Exception:
        db_hits = []

    return _merge_hits(db_hits, facility_hits)
