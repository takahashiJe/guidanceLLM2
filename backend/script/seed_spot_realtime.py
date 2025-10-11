import itertools
import os
from typing import Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from worker.app_db_models import SpotRealtime


DB_USER = os.getenv("APP_DB_USER", "app_user")
DB_PASSWORD = os.getenv("APP_DB_PASSWORD", "app_password")
DB_HOST = os.getenv("APP_DB_HOST", "app-db")
DB_PORT = os.getenv("APP_DB_PORT", "5432")
DB_NAME = os.getenv("APP_DB_NAME", "app_db")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def _generate_seed_rows() -> Iterable[tuple[str, int, int]]:
    """
    spot_001 〜 spot_044 の組を生成する。
    weather / congestion は 0-2 の周期パターンを使い、適度に変化を持たせる。
    """
    weather_cycle = itertools.cycle([0, 1, 2, 1])
    congestion_cycle = itertools.cycle([1, 0, 2, 2, 1])

    for idx in range(1, 45):
        spot_id = f"spot_{idx:03d}"
        yield spot_id, next(weather_cycle), next(congestion_cycle)


def seed_spot_realtime():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        for spot_id, weather, congestion in _generate_seed_rows():
            record = session.get(SpotRealtime, spot_id)
            if record is None:
                record = SpotRealtime(
                    spot_id=spot_id,
                    weather=weather,
                    congestion=congestion,
                )
                session.add(record)
            else:
                record.weather = weather
                record.congestion = congestion

        session.commit()
        print("--- Seeded spot_realtime table with demo values ---")


if __name__ == "__main__":
    seed_spot_realtime()
