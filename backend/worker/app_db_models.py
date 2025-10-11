from sqlalchemy import (
    Column,
    Text,
    BigInteger,
    DateTime,
    func,
    ForeignKey,
    Integer,
    Enum,
    SmallInteger,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, declarative_base
import uuid
import enum

# Alembicなどのマイグレーションツールで管理するため、
# アプリケーションの共通Baseを定義します。
Base = declarative_base()

class LanguageEnum(enum.Enum):
    ja = "ja"
    en = "en"
    zh = "zh"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(Text, unique=True, nullable=False, index=True)
    language = Column(Enum(LanguageEnum), nullable=False, default=LanguageEnum.ja)
    
    # ペルソナモデルの入力となるユーザープロファイル
    user_profile = Column(JSONB) 
    # 現在の周遊計画（spot_idのリスト）
    current_itinerary = Column(JSONB)

    conversations = relationship("Conversation", back_populates="user")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Conversation(Base):
    __tablename__ = "conversations"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    session_id = Column(Text, index=True) # LangGraphのrun_idなどを想定

    role = Column(Text, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    
    # LLMの意図解釈結果などを格納
    meta = Column(JSONB)

    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="conversations")


class SpotRealtime(Base):
    """
    スポットのリアルタイム情報を保持するテーブル。
    weather: 0=晴, 1=曇, 2=雨
    congestion: 0=空き, 1=やや混雑, 2=混雑
    """
    __tablename__ = "spot_realtime"

    spot_id = Column(Text, primary_key=True)
    weather = Column(SmallInteger, nullable=False, server_default="0")
    congestion = Column(SmallInteger, nullable=False, server_default="0")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("weather BETWEEN 0 AND 2", name="ck_spot_realtime_weather"),
        CheckConstraint("congestion BETWEEN 0 AND 2", name="ck_spot_realtime_congestion"),
    )
