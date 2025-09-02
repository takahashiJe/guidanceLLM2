# static_db_models.py
from sqlalchemy import (
    Column, Text, BigInteger, DateTime, func, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry

# 既存の Base をインポートする想定
# from your_project.db import Base

# 共通のJSONスキーマ：
# official_name/aliases/description/social_proof/tags/address は
# いずれも { "ja": ..., "en": ..., "zh": ... } の多言語JSON を想定

class Spot(Base):
    __tablename__ = "spots"

    # 主キー
    spot_id = Column(Text, primary_key=True)

    # カテゴリ（互換性のため保持．テーブル名で区別できるが，
    # 既存データと整合させるため 'tourist_spot' をデフォルトに）
    category = Column(Text, nullable=False, server_default="tourist_spot")

    # 多言語フィールド
    official_name = Column(JSONB, nullable=False)  # {"ja": "...", "en": "...", "zh": "..."}
    aliases       = Column(JSONB)                  # {"ja": [...], "en": [...], "zh": [...]}
    description   = Column(JSONB)                  # {"ja": "...", "en": "...", "zh": "..."}
    social_proof  = Column(JSONB)                  # {"ja": "...", "en": "...", "zh": "..."}
    tags          = Column(JSONB)                  # {"ja": [...], "en": [...], "zh": [...]}
    address       = Column(JSONB)                  # {"ja": "...", "en": "...", "zh": "..."}

    # OSM識別子
    osm_place_id = Column(BigInteger)
    osm_type     = Column(Text)     # "node" | "way" | "relation" など
    osm_id       = Column(BigInteger)

    # RAG 紐付けキー（拡張子なしのMD名）．NULL可
    md_slug = Column(Text, index=True, unique=False, nullable=True)

    # 位置情報（PostGIS）— POINT(lon, lat), SRID=4326
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    # 監査列
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # 推奨インデックス（DDLは下の Alembic 例を参照）
    __table_args__ = (
        # GIST 空間インデックス
        Index("idx_spots_geom_gist", "geom", postgresql_using="gist"),
        # JSONB 検索用 GIN（名前・別名・タグに対して）
        Index("idx_spots_official_name_gin", "official_name", postgresql_using="gin"),
        Index("idx_spots_aliases_gin", "aliases", postgresql_using="gin"),
        Index("idx_spots_tags_gin", "tags", postgresql_using="gin"),
        # md_slug の部分ユニーク（NULL を許容／"None" 文字列は禁止）
        # Alembic側で postgresql_where を使って作成する（後述）
    )


class Facility(Base):
    __tablename__ = "facilities"

    # 主キー
    spot_id = Column(Text, primary_key=True)  # JSONのキー名をそのまま利用（互換のため）

    # カテゴリ（互換性のため保持）
    category = Column(Text, nullable=False, server_default="accommodation")

    # 多言語フィールド
    official_name = Column(JSONB, nullable=False)
    aliases       = Column(JSONB)
    description   = Column(JSONB)
    social_proof  = Column(JSONB)
    tags          = Column(JSONB)
    address       = Column(JSONB)

    # OSM識別子
    osm_place_id = Column(BigInteger)
    osm_type     = Column(Text)
    osm_id       = Column(BigInteger)

    # RAG 紐付けキー
    md_slug = Column(Text, index=True, unique=False, nullable=True)

    # 位置情報（PostGIS）
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    # 監査列
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_facilities_geom_gist", "geom", postgresql_using="gist"),
        Index("idx_facilities_official_name_gin", "official_name", postgresql_using="gin"),
        Index("idx_facilities_aliases_gin", "aliases", postgresql_using="gin"),
        Index("idx_facilities_tags_gin", "tags", postgresql_using="gin"),
        # md_slug の部分ユニークは Alembic で作成（後述）
    )

class AccessPoint(Base):
    """
    アクセスポイント（主に駐車場）の情報を格納するテーブル。
    GeoJSONからインポートされることを想定。
    """
    __tablename__ = "access_points"

    # 主キー: 自動採番の整数ID
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # OpenStreetMap由来のID
    osm_id = Column(BigInteger, index=True)
    osm_type = Column(Text, index=True) # "way", "node" など

    # 名称 (NULLを許容)
    name = Column(Text, nullable=True)

    # その他の属性を格納するJSONBカラム
    properties = Column(JSONB)

    # 位置情報: PostGISのGeometry型 (POINT, SRID=4326)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    # 監査列
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        # 空間インデックス (最寄り検索を高速化)
        Index("idx_access_points_geom", "geom", postgresql_using="gist"),
    )