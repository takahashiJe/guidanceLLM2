from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
try:
    # pydantic v2
    from pydantic import ConfigDict
    _V2 = True
except Exception:
    _V2 = False

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
    format: Optional[str]

class SegmentIndex(BaseModel):
    mode: Literal["car", "foot"]
    start_idx: int
    end_idx: int

class PlanResponse(BaseModel):
    pack_id: str
    route: Dict[str, Any]
    polyline: List[List[float]]
    segments: List[SegmentIndex]

    legs: List[Leg]
    along_pois: List[AlongPoi]
    assets: List[Asset]

    # ★ 将来の追加キーを落とさない（polyline/segments未定義の版でも安全）
    if _V2:
        model_config = ConfigDict(extra="allow")
    else:
        class Config:
            extra = "allow"
