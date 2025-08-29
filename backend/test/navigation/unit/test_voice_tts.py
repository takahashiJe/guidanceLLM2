from pathlib import Path
from backend.worker.app.services.voice import tts

def test_tts_synthesize__di_engine_returns_bytes():
    # synthesize は engine DI を受け取り、その戻りを bytes として返す前提
    def fake_engine(text, language, voice):
        return b"\x00\x01\x02\x03"
    data = tts.synthesize("hello", "ja", "guide_female_1", engine=fake_engine)
    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 0

def test_write_mp3__creates_file_and_returns_meta(tmp_path: Path):
    data = b"\x00\x01\x02\x03\x04\x05"
    rel_url, nbytes, duration = tts.write_mp3(tmp_path, "A", "ja", data)
    # ファイルが作成され、メタが返る
    assert rel_url.endswith("/A.ja.mp3")
    out_path = tmp_path / "A.ja.mp3"
    assert out_path.exists() and out_path.is_file()
    assert nbytes == len(data)
    assert isinstance(duration, float) and duration >= 0.0
