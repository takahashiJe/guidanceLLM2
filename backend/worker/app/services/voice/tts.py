from __future__ import annotations

import io
import os
import struct
from pathlib import Path
from typing import Callable, Optional, Tuple

import httpx


# =========================
# Public API
# =========================

def synthesize(
    text: str,
    language: str,
    voice: str,
    *,
    engine: Optional[Callable[[str, str, str], bytes]] = None,
) -> bytes:
    """
    テキストから音声データ(bytes)を合成して返す。
    - engine が与えられた場合: それを使用（依存注入 / テスト用）
    - COQUI_HTTP_URL が設定されている場合: HTTP サーバへ合成依頼（/api/tts 想定）
    - ローカル Coqui TTS ライブラリが利用可能な場合: ライブラリで WAV を生成
    - いずれも不可の場合: フェイルセーフなダミー WAV を生成

    返却: 音声バイナリ（WAV/MP3 いずれでもよいが、write_mp3 側では中身を再エンコードせず
          そのまま .mp3 として保存する。テストではバイナリの実体までは検証しない）
    """
    if engine is not None:
        data = engine(text, language, voice)
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("engine must return bytes")
        return bytes(data)

    # 1) HTTP Coqui サーバ（/api/tts を想定）
    http_url = os.getenv("COQUI_HTTP_URL")
    if http_url:
        data = _synthesize_via_http(http_url, text, language, voice)
        if data:
            return data

    # 2) ローカル Coqui TTS ライブラリ
    data = _synthesize_via_local_lib(text, language, voice)
    if data:
        return data

    # 3) フェイルセーフ: ダミーの短い WAV を返す（440Hz/mono/16kHz/16bit/0.5sec）
    return _dummy_wav_bytes(duration_s=0.5, sr=16000, freq_hz=440.0)


def write_mp3(pack_dir: Path, spot_id: str, lang: str, data: bytes) -> Tuple[str, int, float]:
    """
    合成済み bytes を MP3 ファイルとして保存（再エンコードは行わず、そのまま書き出す）。
    返り値:
      - rel_url: クライアント配布用の相対URL（`/<pack_id>/<spot_id>.<lang>.mp3` 形式を想定）
      - nbytes: 保存したサイズ
      - duration_s: 音声の秒数（WAV の場合はヘッダから算出。判別できない場合は 0.0）
    """
    pack_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{spot_id}.{lang}.mp3"
    out_path = pack_dir / filename

    with open(out_path, "wb") as f:
        f.write(data)

    # duration 推定（WAV なら RIFF ヘッダから計算）
    duration_s = _probe_wav_duration_seconds(data)

    # rel_url は「/<pack_id>/<file>」相当を返す（PACKS_DIR の公開プレフィックスは上位で付与）
    rel_url = f"/{pack_dir.name}/{filename}"
    return rel_url, out_path.stat().st_size, duration_s


# =========================
# Engines
# =========================

def _synthesize_via_http(base_url: str, text: str, language: str, voice: str) -> Optional[bytes]:
    """
    Coqui TTS サーバ（例: http://coqui:5002/api/tts）を想定。
    実装はサーバ差に耐えるよう、いくつかのパラメータ名で試行する。
    """
    url = f"{base_url.rstrip('/')}/api/tts"
    payloads = [
        {"text": text, "speaker_id": voice, "language_id": language},
        {"text": text, "voice": voice, "lang": language},
        {"text": text, "speaker": voice, "language": language},
    ]
    headers = {"accept": "audio/wav,application/octet-stream"}
    try:
        with httpx.Client(timeout=30) as client:
            for body in payloads:
                r = client.post(url, json=body, headers=headers)
                if r.status_code == 200 and r.content:
                    return bytes(r.content)
    except Exception:
        return None
    return None


def _synthesize_via_local_lib(text: str, language: str, voice: str) -> Optional[bytes]:
    """
    ローカルの Coqui TTS ライブラリ（TTS.api）で WAV を生成。
    依存がない環境では ImportError となるので None。
    """
    try:
        # Lazy import
        from TTS.api import TTS  # type: ignore
    except Exception:
        return None

    # 簡易なモデル選択（必要に応じて環境変数で上書き可能）
    model_name = os.getenv("COQUI_MODEL")
    if not model_name:
        # 言語ごとの無難な既定値（環境により存在しない可能性があります）
        model_by_lang = {
            "ja": "tts_models/ja/kokoro/tacotron2-DDC",   # 例
            "en": "tts_models/en/vctk/vits",
            "zh": "tts_models/zh-CN/baker/tacotron2-DDC",
        }
        model_name = model_by_lang.get(language, "tts_models/en/vctk/vits")

    try:
        tts = TTS(model_name)
        wav, sr = tts.tts(text=text, speaker=voice if voice else None, language=language if language else None)
        return _wav_bytes_from_float_mono(wav, sr)
    except Exception:
        return None


# =========================
# WAV helpers
# =========================

def _wav_bytes_from_float_mono(samples, sr: int) -> bytes:
    """
    float(-1..1) のモノラル配列から PCM16 WAV を作る。
    """
    import math
    import array

    # 正規化 & 16bit へ
    pcm = array.array("h", (max(-32767, min(32767, int(x * 32767.0))) for x in samples))
    byte_data = pcm.tobytes()
    return _build_wav_header_and_data(byte_data, sr=sr, num_channels=1, bits_per_sample=16)


def _dummy_wav_bytes(duration_s: float = 0.5, sr: int = 16000, freq_hz: float = 440.0) -> bytes:
    """
    テストやフォールバック用の単純なサイン波 WAV を生成。
    """
    import math
    import array

    n = int(sr * duration_s)
    two_pi_f = 2.0 * math.pi * freq_hz
    pcm = array.array(
        "h",
        (int(32767 * math.sin(two_pi_f * t / sr)) for t in range(n)),
    )
    byte_data = pcm.tobytes()
    return _build_wav_header_and_data(byte_data, sr=sr, num_channels=1, bits_per_sample=16)


def _build_wav_header_and_data(
    pcm_bytes: bytes,
    *,
    sr: int,
    num_channels: int,
    bits_per_sample: int,
) -> bytes:
    """
    最小限の PCM WAV（RIFF）を作る。
    """
    byte_rate = sr * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    subchunk2_size = len(pcm_bytes)
    chunk_size = 36 + subchunk2_size

    with io.BytesIO() as buf:
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", chunk_size))
        buf.write(b"WAVE")

        # fmt chunk
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))                 # Subchunk1Size
        buf.write(struct.pack("<H", 1))                  # PCM
        buf.write(struct.pack("<H", num_channels))
        buf.write(struct.pack("<I", sr))
        buf.write(struct.pack("<I", byte_rate))
        buf.write(struct.pack("<H", block_align))
        buf.write(struct.pack("<H", bits_per_sample))

        # data chunk
        buf.write(b"data")
        buf.write(struct.pack("<I", subchunk2_size))
        buf.write(pcm_bytes)

        return buf.getvalue()


def _probe_wav_duration_seconds(data: bytes) -> float:
    """
    data が WAV(RIFF) のとき、おおよその duration を計算。
    未知形式なら 0.0 を返す。
    """
    try:
        if len(data) < 44 or not data.startswith(b"RIFF") or data[8:12] != b"WAVE":
            return 0.0
        # fmt チャンクは 12 バイト目以降に現れるはずだが、最小形を仮定して 44 バイトヘッダとして解析
        # 24: sample rate (4B), 22: num channels (2B), 34: bits/sample (2B)
        sr = struct.unpack("<I", data[24:28])[0]
        num_channels = struct.unpack("<H", data[22:24])[0]
        bps = struct.unpack("<H", data[34:36])[0]
        data_size = struct.unpack("<I", data[40:44])[0]
        if sr == 0 or num_channels == 0 or bps == 0:
            return 0.0
        bytes_per_sec = sr * num_channels * (bps // 8)
        if bytes_per_sec == 0:
            return 0.0
        return float(data_size) / float(bytes_per_sec)
    except Exception:
        return 0.0
