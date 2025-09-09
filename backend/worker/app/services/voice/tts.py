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
    import TTS.tts.configs.xtts_config
    from TTS.tts.models.xtts import XttsAudioConfig
    from TTS.config.shared_configs import BaseDatasetConfig
    # PyTorch 2.6+ のセキュリティエラー(UnpicklingError)対策
    torch.serialization.add_safe_globals([
        XttsConfig, 
        TTS.tts.configs.xtts_config.XttsConfig, 
        XttsAudioConfig,
        BaseDatasetConfig,
    ])
    # torch.serialization.add_safe_globals([XttsConfig])
    
    _HAS_COQUI = True

except Exception as e:
    logger.warning(f"Failed to import Coqui TTS or apply patch: {e}. Voice synthesis will fall back to sine wave.")
    _HAS_COQUI = False

# _SERVICE_ROOT_DIR = Path(__file__).parent.resolve()
# _TORCH_PATCH_FILE = _SERVICE_ROOT_DIR / "torch_patch.py"
# _TORCH_PATCH_FILE = Path("/opt/torch_patch.py")
_TORCH_PATCH_FILE = Path("/opt/torch_patch.py")

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
    """汎用サブプロセス実行（タイムアウト・環境変数パッチ適用付き）"""
    
    # diagnostic_path = Path("/opt/torch_patch.py")
    # path_exists = diagnostic_path.exists()
    # raise RuntimeError(f"[DIAGNOSTIC_CHECK] Path checked: {diagnostic_path}, Path.exists() returned: {path_exists}")

    if isinstance(input_bytes, Path):
        input_bytes = input_bytes.read_bytes()
    elif isinstance(input_bytes, str):
        input_bytes = input_bytes.encode("utf-8")
    
    # 1. パッチファイルの「文字列パス」を変数として定義
    patch_path_str = str(_TORCH_PATCH_FILE)

    # 2. 現在の環境変数をコピー
    env = os.environ.copy()

    # 3. パッチファイルが存在するかチェック
    if _TORCH_PATCH_FILE.exists():
        env["PYTHONSTARTUP"] = patch_path_str
        # デバッグログ①：パッチを注入することをログに出力（これがログに出るはず）
        logger.info(f"DEBUG: Injecting PYTHONSTARTUP env: {patch_path_str}")
    else:
        # デバッグログ①'：ファイルが見つからなかった場合（lsの結果から、これは出ないはず）
        logger.warning(
            f"Torch patch file NOT FOUND at {patch_path_str}. "
            "Subprocess TTS CLI will likely fail with UnpicklingError."
        )
        
    try:
        # 4. 修正した環境変数(env=env)を使ってサブプロセスを実行
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if input_bytes is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        out, err = p.communicate(input=input_bytes) # タイムアウトは一旦削除（元のコードに合わせて）

    except Exception as e:
        # Popenやcommunicate自体が失敗した場合
        logger.error(f"Subprocess execution failed BEFORE return code check. Error: {e}")
        raise RuntimeError(f"Subprocess Popen/Communicate failed: {e}") from e

    # 5. サブプロセスから返された標準エラー出力(stderr)をデコード
    err_decoded = err.decode(errors='ignore')

    # デバッグログ②：サブプロセスのstderrをすべて出力
    # （ここに torch_patch.py のログ「patch applied successfully」が含まれているかを調査）
    logger.info(f"DEBUG: Subprocess stderr capture:\n---\n{err_decoded}\n---")

    # 6. リターンコードのチェック
    if p.returncode != 0:
        # サブプロセスがエラー終了した場合
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
    WAV バイト列で返す（...中略...）
    """
    runtime.ensure_loaded()

    # 1) Coqui Python API
    if runtime.coqui_ready and runtime._coqui_model is not None:
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                out_path = Path(td) / "out.wav"

                # API呼び出し用のkwargsを準備
                kwargs: Dict[str, Any] = {}
                
                # 話者があれば指定（★このロジックを元に戻す）
                # (APIは speaker=ID を受け取らないので、これは意図的にAPI呼び出しを失敗させ、
                #  speaker_idx を使えるCLIフォールバック(Strategy 2)に進むためのロジック）
                spk = runtime.cfg.select_voice(language)
                if spk:
                    kwargs["speaker"] = spk

                # API 差異を吸収 (この呼び出しは "speaker=ja_female_1" を解釈できず TypeError となる)
                try:
                    runtime._coqui_model.tts_to_file(
                        text=text,
                        file_path=str(out_path),
                        **kwargs,
                    )
                except TypeError:
                    # モデルによっては text_lang を要求 (ここでも TypeError が発生)
                    runtime._coqui_model.tts_to_file(
                        text=text,
                        file_path=str(out_path),
                        speaker=spk if spk else None,
                        language=language,
                    )

                return out_path.read_bytes()
        except Exception as e1:
            # ★APIが失敗すると、ここに入り、Strategy 2 (CLI) に進む (これが期待動作)
            logger.exception(f"TTS(API) failed. Attempting CLI fallback. Error: {e1}")
            pass

    # 2) Coqui CLI（`tts` コマンド）
    if shutil_which("tts"):
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                out_path = Path(td) / "out.wav"
                cli_args = [
                    "tts",  # sys.argv[0] プレースホルダー
                    "--text", text,
                    "--model_name", runtime.cfg.model_name,
                    "--out_path", str(out_path),
                ]
                spk = runtime.cfg.select_voice(language)
                if spk:
                    cli_args += ["--speaker_idx", spk]

                # [修正] 実行するPythonコードの文字列を定義
                
                # 1. torch_patch.py と同じパッチコード
                patch_code = r"""
                import sys, inspect, torch, torch.serialization
                import TTS.tts.models.xtts as xtts_mod
                from TTS.tts.configs.xtts_config import XttsConfig
                from TTS.tts.models.xtts import XttsAudioConfig
                try:
                    from TTS.config.shared_configs import BaseDatasetConfig, BaseAudioConfig
                except Exception:
                    from TTS.config.shared_configs import BaseDatasetConfig
                    BaseAudioConfig = None

                allow = set()
                for name in dir(xtts_mod):
                    obj = getattr(xtts_mod, name, None)
                    if inspect.isclass(obj) and (name.endswith('Args') or name.endswith('Config') or name.endswith('AudioConfig')):
                        allow.add(obj)

                allow.update({XttsConfig, XttsAudioConfig, getattr(xtts_mod, 'XttsArgs', None), BaseDatasetConfig})
                if BaseAudioConfig is not None:
                    allow.add(BaseAudioConfig)

                torch.serialization.add_safe_globals([c for c in allow if c is not None])
                """
                # 実行コードの先頭に連結して -c に渡す
                code = patch_code + "; " + \
                    f"import sys; sys.argv={argv_repr}; from TTS.bin.synthesize import main; raise SystemExit(main())"
                cmd = ["python", "-c", code]

                
                # 2. 'tts' コマンドが内部的に実行している main 関数を呼び出すコード
                run_code = (
                    "import sys; "
                    "from TTS.bin.synthesize import main; "
                    "sys.exit(main());" # ttsコマンドと同様にmain()を実行
                )

                # [修正] python -c を使って、引数をセットし、パッチと本体を実行するコマンドを構築
                cmd = [
                    "python",
                    "-c",
                    (
                        f"import sys; sys.argv = {cli_args!r}; " # !r は Pythonリストを文字列として安全に埋め込む
                        f"{patch_code} "
                        f"{run_code}"
                    )
                ]

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
