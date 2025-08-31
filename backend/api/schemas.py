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


class Asset(BaseModel):
    spot_id: str
    audio_url: Optional[str] = None
    text_url: Optional[str] = None
    bytes: Optional[int] = None
    duration_s: Optional[float] = None
    # 将来: format: Optional[Literal["mp3","wav"]] = None


class PlanResponse(BaseModel):
    """
    nav → Gateway → Frontend で共有する出力スキーマ。
    """
    pack_id: str
    route: Dict[str, Any]          # GeoJSON FeatureCollection
    legs: List[Leg]
    along_pois: List[AlongPoi]
    assets: List[Asset]
