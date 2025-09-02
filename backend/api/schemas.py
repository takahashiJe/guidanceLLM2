from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
try:
    # pydantic v2
    from pydantic import ConfigDict, model_validator
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
    # 共通
    spot_id: str
    # 新形（最終形）
    text: Optional[str] = None
    audio: Optional[Audio] = None
    # 旧形（NAV 現行）
    audio_url: Optional[str] = None
    text_url: Optional[str] = None
    bytes: Optional[int] = None
    duration_s: Optional[float] = None
    format: Optional[str] = None

    if _V2:
        model_config = ConfigDict(extra="allow", populate_by_name=True)
    else:
        class Config:
            extra = "allow"

    # 旧形で来たら audio を合成して新形に寄せる
    if _V2:
        @model_validator(mode="after")
        def _normalize_legacy(cls, v: "Asset"):
            if (
                v.audio is None and
                v.audio_url and
                v.bytes is not None and
                v.duration_s is not None and
                v.format
            ):
                v.audio = Audio(
                    url=v.audio_url,
                    size_bytes=v.bytes,
                    duration_sec=v.duration_s,
                    format=v.format if v.format in ("mp3", "wav") else "mp3",
                )
            return v
    else:
        # v1 用（任意・必要なら実装）
        pass

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
