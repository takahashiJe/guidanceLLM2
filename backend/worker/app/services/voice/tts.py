from __future__ import annotations

import io
import os
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal, Dict, Any

import logging
logger = logging.getLogger(__name__)

# Coqui TTS を優先して使う。未導入・失敗時はフォールバック。
try:
    from TTS.api import TTS  # type: ignore
    import torch.serialization
    from TTS.tts.configs.xtts_config import XttsConfig
    # PyTorch 2.6+ のセキュリティエラー(UnpicklingError)対策
    torch.serialization.add_safe_globals([XttsConfig])

    _HAS_COQUI = True

except Exception as e:
    logger.warning(f"Failed to import Coqui TTS or apply patch: {e}. Voice synthesis will fall back to sine wave.")
    _HAS_COQUI = False

_SERVICE_ROOT_DIR = Path(__file__).parent.resolve()
_TORCH_PATCH_FILE = _SERVICE_ROOT_DIR / "torch_patch.py"


# -----------------------
# 設定
# -----------------------
@dataclass
class TTSConfig:
    model_name: str
    voice_ja: Optional[str]
    voice_en: Optional[str]
    voice_zh: Optional[str]
    sample_rate: int = 22050  # フォールバック生成時の SR

    @classmethod
    def from_env(cls) -> "TTSConfig":
        return cls(
            # model_name=os.getenv("COQUI_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2"),
            model_name=os.getenv("COQUI_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2"), 
            voice_ja=os.getenv("VOICE_JA", None),
            voice_en=os.getenv("VOICE_EN", None),
            voice_zh=os.getenv("VOICE_ZH", None),
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


# -----------------------
# ランタイム（Coqui モデルのキャッシュ）
# -----------------------
class TTSRuntime:
    def __init__(self, cfg: TTSConfig):
        self.cfg = cfg
        self._coqui_model = None  # lazy
        self._coqui_ready = False

    @property
    def coqui_ready(self) -> bool:
        return self._coqui_ready

    def _load_coqui(self) -> None:
        if not _HAS_COQUI:
            self._coqui_ready = False
            return
        try:
            # モデルは一度だけロード。XTTS v2 など多言語モデル想定。
            self._coqui_model = TTS(self.cfg.model_name)
            self._coqui_ready = True
        except Exception:
            # ロード失敗時はフォールバックへ
            self._coqui_ready = False

    def ensure_loaded(self) -> None:
        if not self._coqui_ready:
            self._load_coqui()


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
    # 現在の環境変数をコピー
    env = os.environ.copy()

    # PYTHONSTARTUP環境変数を設定し、サブプロセスでもPyTorchパッチが適用されるようにする
    if _TORCH_PATCH_FILE.exists():
        env["PYTHONSTARTUP"] = str(_TORCH_PATCH_FILE)
        logger.debug(f"Injecting PYTHONSTARTUP={_TORCH_PATCH_FILE} for subprocess.")
    else:
        # この警告が出た場合、DockerfileのCOPY漏れかパス間違い
        logger.warning(
            f"Torch patch file not found at {_TORCH_PATCH_FILE}. "
            "Subprocess TTS CLI will likely fail with UnpicklingError."
        )
        
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if input_bytes is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    out, err = p.communicate(input=input_bytes)
    if p.returncode != 0:
        raise RuntimeError(f"subprocess failed: {' '.join(cmd)}\n{err.decode(errors='ignore')}")
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
    WAV バイト列で返す（最終的な保存フォーマットは呼び出し側で ffmpeg に渡す）。
    1) Coqui（Python API） → 2) Coqui CLI → 3) フォールバックの順で試行。
    """
    runtime.ensure_loaded()

    # 1) Coqui Python API
    if runtime.coqui_ready and runtime._coqui_model is not None:
        try:
            # XTTS v2 は多言語合成が可能。必要なら speaker_wav / speaker_id を追加。
            # python API は基本ファイル出力なので、一旦 temp へ出してから読む。
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                out_path = Path(td) / "out.wav"
                # language 引数を accept するモデルなら渡す（XTTS v2 は text_lang が必要なケースあり）
                kwargs: Dict[str, Any] = {}
                # 話者があれば指定（モデルによって指定方法が異なる場合あり）
                spk = runtime.cfg.select_voice(language)
                if spk:
                    kwargs["speaker"] = spk

                # API 差異を吸収
                try:
                    runtime._coqui_model.tts_to_file(
                        text=text,
                        file_path=str(out_path),
                        **kwargs,
                    )
                except TypeError:
                    # モデルによっては text_lang を要求
                    runtime._coqui_model.tts_to_file(
                        text=text,
                        file_path=str(out_path),
                        speaker=spk if spk else None,
                        language=language,
                    )

                return out_path.read_bytes()
        except Exception as e1:
            logger.exception(f"TTS(API) failed. Attempting CLI fallback. Error: {e1}")
            pass

    # 2) Coqui CLI（`tts` コマンド）
    #    例: tts --text "こんにちは" --model_name tts_models/multilingual/multi-dataset/xtts_v2 --out_path out.wav
    if shutil_which("tts"):
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                out_path = Path(td) / "out.wav"
                cmd = [
                    "tts",
                    "--text", text,
                    "--model_name", runtime.cfg.model_name,
                    "--out_path", str(out_path),
                ]
                # 話者指定（モデルにより有効/無効）
                spk = runtime.cfg.select_voice(language)
                if spk:
                    cmd += ["--speaker_idx", spk]

                _run_subprocess(cmd)
                return out_path.read_bytes()
        except Exception as e2:
            logger.exception(f"TTS(CLI) failed. Using sine wave fallback. Error: {e2}")
            pass

    # 3) フォールバック：簡易WAV（1秒）
    return _sine_wav(duration_sec=1.0, sr=runtime.cfg.sample_rate, freq=440.0)


def shutil_which(name: str) -> Optional[str]:
    from shutil import which
    return which(name)
