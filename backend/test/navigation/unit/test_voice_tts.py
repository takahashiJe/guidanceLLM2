import io
import os
import shutil
import wave

import pytest

# テスト対象：低レベルTTSユーティリティ
from backend.worker.app.services.voice.tts import (
    TTSConfig,
    TTSRuntime,
    synthesize_wav_bytes,
    estimate_wav_duration_sec,
    ffmpeg_convert_wav_to_mp3,
    shutil_which,
)


def _make_runtime():
    cfg = TTSConfig.from_env()
    return TTSRuntime(cfg)


def test_synthesize_wav_bytes_returns_wav():
    rt = _make_runtime()
    wav = synthesize_wav_bytes(rt, text="テスト音声です。", language="ja")
    # WAVヘッダ存在
    assert isinstance(wav, (bytes, bytearray))
    assert len(wav) > 44
    # duration算出できる
    dur = estimate_wav_duration_sec(wav)
    assert dur >= 0.0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available in test env")
def test_ffmpeg_convert_wav_to_mp3_success_when_ffmpeg_exists():
    rt = _make_runtime()
    wav = synthesize_wav_bytes(rt, text="mp3変換テストです。", language="ja")
    mp3 = ffmpeg_convert_wav_to_mp3(wav, bitrate_kbps=64)
    # mp3はWAVより小さくなるとは限らないが、バイト列として有効かを見る
    assert isinstance(mp3, (bytes, bytearray))
    assert len(mp3) > 0


def test_estimate_wav_duration_sec_valid():
    # 1ch/16bit/22050Hzで約0.5秒のWAVを即席生成
    sr = 22050
    dur_sec = 0.5
    n = int(sr * dur_sec)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * n)

    est = estimate_wav_duration_sec(buf.getvalue())
    assert 0.45 <= est <= 0.55
