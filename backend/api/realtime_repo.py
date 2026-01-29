from __future__ import annotations

from sqlalchemy.orm import Session

from backend.worker.app_db_models import SpotRealtime


def get_spot_realtime(db: Session, spot_id: str) -> SpotRealtime | None:
    """スポットのリアルタイム情報を取得する"""
    return db.get(SpotRealtime, spot_id)


def upsert_spot_realtime(
    db: Session,
    spot_id: str,
    weather: int,
    congestion: int,
) -> SpotRealtime:
    """スポットのリアルタイム情報を挿入または更新し、保存後のレコードを返す"""
    weather = max(0, min(2, int(weather)))
    congestion = max(0, min(2, int(congestion)))

    record = db.get(SpotRealtime, spot_id)
    if record is None:
        record = SpotRealtime(
            spot_id=spot_id,
            weather=weather,
            congestion=congestion,
        )
        db.add(record)
    else:
        record.weather = weather
        record.congestion = congestion

    db.commit()
    db.refresh(record)
    return record
