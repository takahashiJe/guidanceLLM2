# 統合テスト用の共通フィクスチャ
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# このファイルは backend/test/navigation/integration/ 配下にある想定
ROOT = Path(__file__).resolve().parents[4]  # → プロジェクトルート
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def client_routing():
    from backend.worker.app.services.routing.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def client_alongpoi():
    from backend.worker.app.services.alongpoi.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def client_llm():
    from backend.worker.app.services.llm.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def client_voice(tmp_path_factory, monkeypatch):
    # voice サービスが保存先を参照する場合に備えて PACKS_DIR をテスト専用に設定
    packs_dir = tmp_path_factory.mktemp("packs")
    monkeypatch.setenv("PACKS_DIR", str(packs_dir))
    from backend.worker.app.services.voice.main import app
    return TestClient(app)


# 以下，サンプル入力（unit 側と同等）
@pytest.fixture
def sample_waypoints():
    # (lat, lon) 順。routing 側で lon,lat に並べ替える前提
    # current → A → B → C → current
    return [
        {"lat": 39.2000, "lon": 139.9000, "spot_id": "current"},
        {"lat": 39.3000, "lon": 139.9500, "spot_id": "A"},
        {"lat": 39.3500, "lon": 139.9800, "spot_id": "B"},
        {"lat": 39.2500, "lon": 139.9600, "spot_id": "C"},
        {"lat": 39.2000, "lon": 139.9000, "spot_id": "current"},
    ]


@pytest.fixture
def simple_polyline():
    # lon,lat の折れ線（OSRM準拠）
    return [
        [139.9000, 39.2000],
        [139.9250, 39.2250],
        [139.9500, 39.2500],
        [139.9750, 39.2750],
    ]


@pytest.fixture
def simple_segments():
    # polyline のインデックス範囲をレッグに対応付ける
    return [
        {"mode": "car", "start_idx": 0, "end_idx": 1},
        {"mode": "foot", "start_idx": 1, "end_idx": 3},
    ]


@pytest.fixture
def poi_hits_near_first_leg():
    return [
        {"spot_id": "D", "name": "Spot D", "lon": 139.9100, "lat": 39.2100},
        {"spot_id": "E", "name": "Spot E", "lon": 139.9150, "lat": 39.2150},
    ]
