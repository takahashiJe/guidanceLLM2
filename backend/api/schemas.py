from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class Coord(BaseModel):
    lat: float
    lon: float


class SpotPick(BaseModel):
    spot_id: str


class PlanRequest(BaseModel):
    """
    Frontend → Gateway（→ nav）で共有する入力スキーマ。
    """
    language: Literal["ja", "en", "zh"]
    origin: Coord
    return_to_origin: bool = True
    waypoints: List[SpotPick] = Field(..., min_items=1)


class Leg(BaseModel):
    mode: Literal["car", "foot"]
    # Pydanticのキーワード衝突回避のため alias を使用
    from_: Coord = Field(..., alias="from")
    to: Coord
    distance_m: float
    duration_s: float


class AlongPoi(BaseModel):
    spot_id: str
    name: str
    lon: float
    lat: float
    kind: Literal["spot", "facility"]
    md_slug: Optional[str] = None
    description: Optional[str] = None


class Audio(BaseModel):
    url: str
    size_bytes: int
    duration_sec: float
    format: Literal["mp3", "wav"]

class Asset(BaseModel):
    spot_id: str
    text: str # text_urlからtextに変更
    audio: Optional[Audio] = None


class PlanResponse(BaseModel):
    """
    nav → Gateway → Frontend で共有する出力スキーマ。
    """
    pack_id: str
    route: Dict[str, Any]          # GeoJSON FeatureCollection
    polyline: List[List[float]]
    segments: List[Dict[str, Any]]
    legs: List[Leg]
    along_pois: List[AlongPoi]
    assets: List[Asset]
