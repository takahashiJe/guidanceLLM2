from __future__ import annotations

import io
import os
import struct
import subprocess
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
    優先順位: engine 注入 > COQUI_HTTP_URL > ローカルCoqui > ダミーWAV
    """
    if engine is not None:
        data = engine(text, language, voice)
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("engine must return bytes")
        return bytes(data)

    http_url = os.getenv("COQUI_HTTP_URL")
    if http_url:
        data = _synthesize_via_http(http_url, text, language, voice)
        if data:
            return data

    data = _synthesize_via_local_lib(text, language, voice)
    if data:
        return data

    return _dummy_wav_bytes(duration_s=0.5, sr=16000, freq_hz=440.0)


def save_audio(
    pack_dir: Path,
    spot_id: str,
    lang: str,
    data: bytes,
    *,
    preferred_format: str = "mp3",
    bitrate_kbps: int = 64,
) -> Tuple[str, int, float, str]:
    """
    音声 bytes を希望フォーマットに合わせて保存し、URL/サイズ/秒数/実フォーマットを返す。
    - preferred_format が "mp3" のとき:
        data が WAV なら ffmpeg で MP3(単純CBR) に変換（失敗時は WAV で保存）
        data が MP3 ならそのまま保存
      "wav" のときはそのまま保存。
    """
    pack_dir.mkdir(parents=True, exist_ok=True)

    # まず data が WAV か MP3 かを判定
    is_wav = _is_wav(data)
    is_mp3 = _is_mp3(data)

    # WAV の場合、事前に duration を計算可能
    wav_duration = _probe_wav_duration_seconds(data) if is_wav else 0.0

    if preferred_format == "mp3":
        # すでに MP3 ならそのまま保存
        if is_mp3:
            filename = f"{spot_id}.{lang}.mp3"
            out_path = pack_dir / filename
            out_path.write_bytes(data)
            rel_url = f"/packs/{pack_dir.name}/{filename}"
            return rel_url, out_path.stat().st_size, wav_duration or 0.0, "mp3"

        # WAV → MP3 変換を試みる
        if is_wav:
            mp3_bytes = _transcode_wav_to_mp3_bytes(data, bitrate_kbps=bitrate_kbps)
            if mp3_bytes:
                filename = f"{spot_id}.{lang}.mp3"
                out_path = pack_dir / filename
                out_path.write_bytes(mp3_bytes)
                rel_url = f"/packs/{pack_dir.name}/{filename}"
                # duration は WAV 由来を採用
                return rel_url, out_path.stat().st_size, wav_duration or 0.0, "mp3"
            # 変換失敗 → WAV のまま保存
            return write_wav(pack_dir, spot_id, lang, data) + ("wav",)

        # 形式不明 → そのまま mp3 拡張子で保存せず、WAVで保存して安全側に倒す
        return write_wav(pack_dir, spot_id, lang, data) + ("wav",)

    # preferred_format != "mp3" → WAV で保存
    return write_wav(pack_dir, spot_id, lang, data) + ("wav",)


def write_mp3(pack_dir: Path, spot_id: str, lang: str, data: bytes) -> Tuple[str, int, float]:
    """
    後方互換のため温存。新規コードは save_audio(...) の利用を推奨。
    data を MP3 としてそのまま保存し、URL/サイズ/秒数(不明なら0.0) を返す。
    """
    pack_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{spot_id}.{lang}.mp3"
    out_path = pack_dir / filename
    out_path.write_bytes(data)
    rel_url = f"/packs/{pack_dir.name}/{filename}"
    # WAV なら秒数を読めるが、ここでは 0.0 を返す（互換のため）
    return rel_url, out_path.stat().st_size, 0.0


def write_wav(pack_dir: Path, spot_id: str, lang: str, data: bytes) -> Tuple[str, int, float]:
    """
    data を WAV として保存し、URL/サイズ/秒数を返す。
    """
    pack_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{spot_id}.{lang}.wav"
    out_path = pack_dir / filename
    out_path.write_bytes(data)
    rel_url = f"/packs/{pack_dir.name}/{filename}"
    dur = _probe_wav_duration_seconds(data)
    return rel_url, out_path.stat().st_size, dur


# =========================
# Engines
# =========================

def _synthesize_via_http(base_url: str, text: str, language: str, voice: str) -> Optional[bytes]:
    url = f"{base_url.rstrip('/')}/api/tts"
    payloads = [
        {"text": text, "speaker_id": voice, "language_id": language},
        {"text": text, "voice": voice, "lang": language},
        {"text": text, "speaker": voice, "language": language},
    ]
    headers = {"accept": "audio/wav,application/octet-stream,audio/mpeg"}
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
    try:
        from TTS.api import TTS  # type: ignore
    except Exception:
        return None

    model_name = os.getenv("COQUI_MODEL")
    if not model_name:
        model_by_lang = {
            "ja": "tts_models/ja/kokoro/tacotron2-DDC",
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
# Format helpers
# =========================

def _is_wav(data: bytes) -> bool:
    return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE"

def _is_mp3(data: bytes) -> bool:
    if len(data) < 2:
        return False
    if data.startswith(b"ID3"):
        return True
    # MPEG1 Layer III フレームシンク（簡易）
    return data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def _transcode_wav_to_mp3_bytes(data: bytes, bitrate_kbps: int = 64) -> Optional[bytes]:
    """
    ffmpeg をサブプロセスで呼び出し、WAV bytes → MP3 bytes に変換。
    ffmpeg が無い/失敗時は None。
    """
    try:
        cmd = [
            "ffmpeg",
            "-f", "wav",
            "-i", "pipe:0",
            "-vn",
            "-ac", "1",
            "-b:a", f"{int(bitrate_kbps)}k",
            "-f", "mp3",
            "pipe:1",
        ]
        proc = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
        return proc.stdout if proc.returncode == 0 and proc.stdout else None
    except Exception:
        return None


# =========================
# WAV helpers
# =========================

def _wav_bytes_from_float_mono(samples, sr: int) -> bytes:
    import array
    pcm = array.array("h", (max(-32767, min(32767, int(x * 32767.0))) for x in samples))
    byte_data = pcm.tobytes()
    return _build_wav_header_and_data(byte_data, sr=sr, num_channels=1, bits_per_sample=16)


def _dummy_wav_bytes(duration_s: float = 0.5, sr: int = 16000, freq_hz: float = 440.0) -> bytes:
    import math
    import array
    n = int(sr * duration_s)
    two_pi_f = 2.0 * math.pi * freq_hz
    pcm = array.array("h", (int(32767 * math.sin(two_pi_f * t / sr)) for t in range(n)))
    return _build_wav_header_and_data(pcm.tobytes(), sr=sr, num_channels=1, bits_per_sample=16)


def _build_wav_header_and_data(pcm_bytes: bytes, *, sr: int, num_channels: int, bits_per_sample: int) -> bytes:
    byte_rate = sr * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    subchunk2_size = len(pcm_bytes)
    chunk_size = 36 + subchunk2_size
    with io.BytesIO() as buf:
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", chunk_size))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))
        buf.write(struct.pack("<H", 1))
        buf.write(struct.pack("<H", num_channels))
        buf.write(struct.pack("<I", sr))
        buf.write(struct.pack("<I", byte_rate))
        buf.write(struct.pack("<H", block_align))
        buf.write(struct.pack("<H", bits_per_sample))
        buf.write(b"data")
        buf.write(struct.pack("<I", subchunk2_size))
        buf.write(pcm_bytes)
        return buf.getvalue()


def _probe_wav_duration_seconds(data: bytes) -> float:
    try:
        if len(data) < 44 or not data.startswith(b"RIFF") or data[8:12] != b"WAVE":
            return 0.0
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
