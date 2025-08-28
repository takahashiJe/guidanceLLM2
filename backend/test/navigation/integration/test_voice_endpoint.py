import os
from pathlib import Path
import pytest

def test_voice_endpoint__synthesize_and_save(monkeypatch, client_voice, tmp_path):
    from backend.worker.app.services.voice import tts

    # synthesize → ダミー音声
    monkeypatch.setattr(tts, "synthesize", lambda text, language, voice, engine=None: b"\x00\x01\x02\x03\x04", raising=True)
    # write_mp3 → 実ファイルI/Oは避けて戻り値だけ返す
    def fake_save_audio(pack_dir: Path, spot_id: str, lang: str, data: bytes, *, preferred_format="mp3", bitrate_kbps: int = 64):
    rel = f"/packs/GUID/{spot_id}.{lang}.{preferred_format}"
    # duration_s は 1.23 を返す
    return rel, len(data), 1.23, preferred_format
    monkeypatch.setattr(tts, "save_audio", fake_save_audio, raising=True)

    body = {
        "language": "ja",
        "voice": "guide_female_1",
        "text": "ようこそ鳥海山へ。",
        "spot_id": "A",
        "pack_id": "GUID"
    }
    res = client_voice.post("/synthesize", json=body)
    assert res.status_code == 200
    data = res.json()

    assert data["audio_url"].endswith("/packs/GUID/A.ja.mp3")
    assert data["bytes"] == 5
    assert data["duration_s"] == 1.23
    assert data["format"] == "mp3"
