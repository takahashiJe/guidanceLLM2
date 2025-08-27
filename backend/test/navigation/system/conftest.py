# system テスト共通フィクスチャ
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# このファイルは backend/test/navigation/system/ 配下想定
ROOT = Path(__file__).resolve().parents[4]  # → プロジェクトルート
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

@pytest.fixture
def sample_waypoints():
    # current → A → B → C → current
    return [
        {"lat": 39.2000, "lon": 139.9000, "spot_id": "current"},
        {"lat": 39.3000, "lon": 139.9500, "spot_id": "A"},
        {"lat": 39.3500, "lon": 139.9800, "spot_id": "B"},
        {"lat": 39.2500, "lon": 139.9600, "spot_id": "C"},
        {"lat": 39.2000, "lon": 139.9000, "spot_id": "current"},
    ]

@pytest.fixture
def nav_client(monkeypatch, tmp_path):
    """
    nav サービスを TestClient で起動。下流サービスの BASE URL はダミーに。
    """
    # 下流サービスの BASE を nav が読む環境変数に設定
    monkeypatch.setenv("ROUTING_BASE", "http://routing")
    monkeypatch.setenv("ALONGPOI_BASE", "http://alongpoi")
    monkeypatch.setenv("LLM_BASE", "http://llm")
    monkeypatch.setenv("VOICE_BASE", "http://voice")
    # packs の出力先（テキスト保存などを行う場合に備えて）
    monkeypatch.setenv("PACKS_DIR", str(tmp_path / "packs"))

    # nav を後から import（環境変数適用のため）
    from backend.worker.app.services.nav.main import app
    return TestClient(app)
