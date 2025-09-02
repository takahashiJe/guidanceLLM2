import json
import os
import re
import importlib
from pathlib import Path

import pytest
from starlette.testclient import TestClient


def _reload_app_with_packs(tmp_path):
    """
    PACKS_ROOT を一時ディレクトリに向けてから voice.main をリロードし、app を返す。
    app import時にPACKS_ROOTが評価されるため、必ずリロードが必要。
    """
    os.environ["PACKS_ROOT"] = str(tmp_path / "packs")
    from backend.worker.app.services.voice import main as voice_main
    importlib.reload(voice_main)
    return voice_main.app


@pytest.fixture
def client(tmp_path):
    app = _reload_app_with_packs(tmp_path)
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    js = r.json()
    assert js["status"] == "ok"
    assert "packs_root" in js
    assert "model" in js


def test_post_synthesize_basic(client):
    body = {"text": "これはテスト音声です。", "language": "ja", "format": "mp3", "bitrate_kbps": 64}
    r = client.post("/synthesize", json=body)
    assert r.status_code == 200
    js = r.json()
    # /synthesize は保存しない・メタだけ返す
    assert set(js.keys()) == {"size_bytes", "duration_sec", "format"}
    assert js["size_bytes"] > 0
    assert js["duration_sec"] >= 0.0
    assert js["format"] in ("mp3", "wav")  # ffmpeg不在だとwavフォールバック可


def test_synthesize_and_save_batch_creates_files_and_urls(client, tmp_path):
    pack_id = "pack_test_001"
    body = {
        "pack_id": pack_id,
        "language": "ja",
        "preferred_format": "mp3",
        "bitrate_kbps": 64,
        "save_text": True,
        "items": [
            {"spot_id": "spot_A", "text": "スポットAの説明テキストです。"},
            {"spot_id": "spot_B", "text": "スポットBの説明テキストです。"},
        ],
    }
    r = client.post("/synthesize_and_save", json=body)
    assert r.status_code == 200
    js = r.json()
    assert js["pack_id"] == pack_id
    assert js["language"] == "ja"
    assert isinstance(js["items"], list) and len(js["items"]) == 2

    # ファイルが作られているか（PACKS_ROOT 以下）
    packs_root = Path(os.environ["PACKS_ROOT"])
    pack_dir = packs_root / pack_id
    assert pack_dir.exists()

    for it in js["items"]:
        # レスポンス形式の確認
        assert set(it.keys()) >= {"spot_id", "url", "size_bytes", "duration_sec", "format"}
        assert it["size_bytes"] > 0
        assert it["duration_sec"] >= 0.0
        assert it["format"] in ("mp3", "wav")

        # URL 形式チェック: /packs/{pack_id}/{spot_id}.ja.{ext}
        m = re.match(rf"^/packs/{re.escape(pack_id)}/([A-Za-z0-9_\-]+)\.ja\.(mp3|wav)$", it["url"])
        assert m, f"unexpected url format: {it['url']}"

        # 実ファイル存在
        audio_path = pack_dir / Path(it["url"]).name
        assert audio_path.exists()
        assert audio_path.stat().st_size == it["size_bytes"]

        # save_text = True のときは .txt も存在し、text_url が返る
        assert "text_url" in it and it["text_url"] is not None
        txt_path = pack_dir / Path(it["text_url"]).name
        assert txt_path.exists()
        assert txt_path.read_text(encoding="utf-8").strip() != ""


def test_synthesize_and_save_empty_items_400(client):
    body = {
        "pack_id": "pack_empty",
        "language": "ja",
        "preferred_format": "mp3",
        "items": [],
    }
    r = client.post("/synthesize_and_save", json=body)
    assert r.status_code == 400
    assert "items" in r.json()["detail"]
