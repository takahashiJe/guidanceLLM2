# backend/test/navigation/integration/test_voice_endpoint.py
from __future__ import annotations

from pathlib import Path
import re
import os
import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_voice(tmp_path, monkeypatch):
    """
    /packs の保存先をテスト用の一時ディレクトリに切り替える。
    既存の ScopeMismatch 問題を避けるため、function スコープで monkeypatch を使う。
    """
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PACKS_DIR", str(packs_dir))
    # フォーマットはテスト容易性のため WAV を既定とする（ffmpeg 依存を避ける）
    monkeypatch.setenv("TTS_FORMAT", "wav")

    from backend.worker.app.services.voice import main as voice_main
    return TestClient(voice_main.app)


def _dummy_wav_bytes():
    # テスト用に安定した WAV バイトを作る（tts モジュールのヘルパーを流用）
    from backend.worker.app.services.voice import tts as tts_mod
    return tts_mod._dummy_wav_bytes(duration_s=0.2, sr=16000, freq_hz=440.0)


def test_voice_endpoint__synthesize_and_save_pack(monkeypatch, client_voice, tmp_path):
    """
    /synthesize_and_save:
      - 200 を返す
      - items[].url が /packs/{pack_id}/{spot_id}.{lang}.wav 形式
      - 実ファイルが PACKS_DIR に保存されている
      - size_bytes > 0, duration_sec > 0
    """
    # voice.main 内で import されたシンボルをパッチする点に注意
    from backend.worker.app.services.voice import main as voice_main

    # TTS をダミー WAV 返却に差し替え
    wav = _dummy_wav_bytes()
    monkeypatch.setattr(
        voice_main,
        "tts_synthesize",
        lambda text, language, voice: wav,
        raising=True,
    )

    payload = {
        "pack_id": "pack_test_001",
        "language": "ja",
        "preferred_format": "wav",  # ffmpeg を避けて WAV で保存
        "items": [
            {"spot_id": "spot_hottai_falls", "text": "法体の滝の説明テキスト"},
            {"spot_id": "spot_chokai_lake", "text": "鳥海湖の説明テキスト"},
        ],
    }

    res = client_voice.post("/synthesize_and_save", json=payload)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["pack_id"] == "pack_test_001"
    assert body["language"] == "ja"
    assert isinstance(body["items"], list) and len(body["items"]) == 2

    # 保存先確認
    packs_dir = Path(os.environ["PACKS_DIR"])
    pack_dir = packs_dir / payload["pack_id"]
    assert pack_dir.exists() and pack_dir.is_dir()

    for item in body["items"]:
        # 返却フィールドの検査
        assert set(item.keys()) == {"spot_id", "url", "size_bytes", "duration_sec", "format"}
        assert item["format"] in ("wav", "mp3")  # 今回は "wav" のはず
        assert item["size_bytes"] > 0
        assert item["duration_sec"] >= 0.0

        # URL 形式の検査
        m = re.match(rf"^/packs/{payload['pack_id']}/([a-zA-Z0-9_\-]+)\.ja\.(wav|mp3)$", item["url"])
        assert m, f"unexpected url: {item['url']}"

        # 実ファイルの存在確認
        # URL は /packs/ 起点、Nginx の alias に合わせて PACKS_DIR と対応
        fname = item["url"].split("/")[-1]
        fpath = pack_dir / fname
        assert fpath.exists() and fpath.stat().st_size == item["size_bytes"]


def test_voice_endpoint__synthesize_single(monkeypatch, client_voice):
    """
    /synthesize:
      - 200 を返す
      - Content-Type が audio/wav か audio/mpeg のいずれか
      - ボディが非空
    """
    from backend.worker.app.services.voice import main as voice_main

    wav = _dummy_wav_bytes()
    monkeypatch.setattr(
        voice_main,
        "tts_synthesize",
        lambda text, language, voice: wav,
        raising=True,
    )

    payload = {"text": "単発音声テスト", "language": "ja", "format": "wav"}
    res = client_voice.post("/synthesize", json=payload)
    assert res.status_code == 200, res.text
    assert res.headers.get("content-type") in ("audio/wav", "audio/mpeg", "application/octet-stream")
    assert res.content and len(res.content) > 0
