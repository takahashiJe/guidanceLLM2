from __future__ import annotations

import io
import os, re, importlib
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal, Dict, Any


import logging
logger = logging.getLogger(__name__)

# # Coqui TTS を優先して使う。未導入・失敗時はフォールバック。
# try:
#     from TTS.api import TTS as CoquiTTS
#     import torch.serialization
#     from torch.serialization import add_safe_globals, safe_globals
#     from TTS.tts.configs.xtts_config import XttsConfig
#     from TTS.tts.models.xtts import XttsAudioConfig
#     from TTS.config.shared_configs import BaseDatasetConfig
#     # PyTorch 2.6+ のセキュリティエラー(UnpicklingError)対策
#     torch.serialization.add_safe_globals([
#         XttsConfig,
#         XttsAudioConfig,
#         BaseDatasetConfig,
#     ])
#     # torch.serialization.add_safe_globals([XttsConfig])
    
#     _HAS_COQUI = True

# except Exception as e:
#     logger.warning(f"Failed to import Coqui TTS or apply patch: {e}. Voice synthesis will fall back to sine wave.")
#     _HAS_COQUI = False

# _TORCH_PATCH_FILE = Path("/opt/torch_patch.py")

# -----------------------
# 設定
# -----------------------
@dataclass
class TTSConfig:
    model_name: str
    voice_ja: Optional[str]
    voice_en: Optional[str]
    voice_zh: Optional[str]
    voice_ja_ref: Optional[str] = None
    voice_en_ref: Optional[str] = None
    voice_zh_ref: Optional[str] = None
    sample_rate: int = 22050  # フォールバック生成時の SR

    @classmethod
    def from_env(cls) -> "TTSConfig":
        def _p(x: Optional[str]) -> Optional[Path]:
            return Path(x).resolve() if x else None
        return cls(
            model_name=os.getenv("COQUI_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2"),
            voice_ja=os.getenv("VOICE_JA", None),
            voice_en=os.getenv("VOICE_EN", None),
            voice_zh=os.getenv("VOICE_ZH", None),
            voice_ja_ref=os.getenv("VOICE_JA_REF"),
            voice_en_ref=os.getenv("VOICE_EN_REF"),
            voice_zh_ref=os.getenv("VOICE_ZH_REF"),
            sample_rate=int(os.getenv("TTS_SAMPLE_RATE", "22050")),
        )

    def select_voice(self, lang: str) -> Optional[str]:
        if lang == "ja":
            return self.voice_ja
        if lang == "en":
            return self.voice_en
        if lang == "zh":
            return self.voice_zh
        return None
    
    def select_voice_ref(self, lang: str) -> Optional[Path]:
        if lang == "ja":
            return self.voice_ja_ref
        if lang == "en":
            return self.voice_en_ref
        if lang == "zh":
            return self.voice_zh_ref
        return None


# -----------------------
# ランタイム（Coqui モデルのキャッシュ）
# -----------------------
class TTSRuntime:
    def __init__(self, cfg: TTSConfig):
        self.cfg = cfg
        # self._coqui_model = None  # lazy
        # self._coqui_ready = False

    # @property
    # def coqui_ready(self) -> bool:
    #     return self._coqui_ready

    # def _load_coqui(self) -> None:
    #     if not _HAS_COQUI:
    #         self._coqui_ready = False
    #         return
    #     try:
    #         # モデルは一度だけロード。XTTS v2 など多言語モデル想定。
    #         self._coqui_model = _load_xtts(self.cfg.model_name)
    #         self._coqui_ready = True
    #     except Exception:
    #         # ロード失敗時はフォールバックへ
    #         self._coqui_ready = False

    def ensure_loaded(self) -> None:
        # if not self._coqui_ready:
        #     self._load_coqui()
        pass


# -----------------------
# ユーティリティ
# -----------------------
def ensure_packs_root(packs_root: Path) -> None:
    packs_root.mkdir(parents=True, exist_ok=True)

def _sine_wav(duration_sec: float = 1.0, sr: int = 22050, freq: float = 440.0) -> bytes:
    """フォールバック用の簡易WAV（1ch 16bit PCM, 正弦波）。"""
    import math
    n = int(duration_sec * sr)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16bit
        wf.setframerate(sr)
        for i in range(n):
            val = int(32767.0 * math.sin(2.0 * math.pi * freq * (i / sr)))
            wf.writeframesraw(val.to_bytes(2, byteorder="little", signed=True))
    return buf.getvalue()


def estimate_wav_duration_sec(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        sr = wf.getframerate()
        if sr <= 0:
            return 0.0
        return float(frames) / float(sr)


def _run_subprocess(cmd: list[str], input_bytes: Optional[bytes] = None) -> bytes:
    """汎用サブプロセス実行"""
    env = os.environ.copy()
        
    try:
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if input_bytes is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        out, err = p.communicate(input=input_bytes)

    except Exception as e:
        logger.error(f"Subprocess execution failed BEFORE return code check. Error: {e}")
        raise RuntimeError(f"Subprocess Popen/Communicate failed: {e}") from e

    err_decoded = err.decode(errors='ignore')
    logger.info(f"DEBUG: Subprocess stderr capture:\n---\n{err_decoded}\n---")

    if p.returncode != 0:
        logger.error(f"Subprocess returned non-zero code {p.returncode}. Command: {' '.join(cmd)}")
        raise RuntimeError(f"subprocess failed: {' '.join(cmd)}\n{err_decoded}")

    return out


def ffmpeg_convert_wav_to_mp3(wav_bytes: bytes, bitrate_kbps: int = 64) -> bytes:
    """
    ffmpeg を使って WAV → MP3 に変換。
    """
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "wav", "-i", "pipe:0",
        "-b:a", f"{bitrate_kbps}k",
        "-f", "mp3", "pipe:1",
    ]
    return _run_subprocess(cmd, input_bytes=wav_bytes)


def try_ffprobe_duration_sec(media_bytes: bytes) -> Optional[float]:
    """
    ffprobe が使える場合は正確な長さを取得（使えない環境なら None）。
    """
    try:
        cmd = [
            "ffprobe", "-hide_banner", "-loglevel", "error",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "-show_entries", "format=duration",
            "pipe:0",
        ]
        out = _run_subprocess(cmd, input_bytes=media_bytes)
        s = out.decode().strip()
        if not s:
            return None
        return max(0.0, float(s))
    except Exception:
        return None


# -----------------------
# 合成本体
# -----------------------
def synthesize_wav_bytes(runtime: TTSRuntime, text: str, language: Literal["ja", "en", "zh"]) -> bytes:
    """
    WAV バイト列で返す（gTTS移行後は基本的に使われないが、互換性のため残す）
    """
    # フォールバックとして無音のWAVを返す
    return _sine_wav(duration_sec=1.0, sr=runtime.cfg.sample_rate, freq=0)