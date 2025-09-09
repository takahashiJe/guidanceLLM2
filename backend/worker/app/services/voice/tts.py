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

# Coqui TTS を優先して使う。未導入・失敗時はフォールバック。
try:
    from TTS.api import TTS  # type: ignore
    import torch.serialization
    from torch.serialization import safe_globals
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
    voice_ja_ref: Optional[str] = None
    voice_en_ref: Optional[str] = None
    voice_zh_ref: Optional[str] = None
    sample_rate: int = 22050  # フォールバック生成時の SR

    @classmethod
    def from_env(cls) -> "TTSConfig":
        def _p(x: Optional[str]) -> Optional[Path]:
            return Path(x).resolve() if x else None
        return cls(
            # model_name=os.getenv("COQUI_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2"),
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
_ALLOWED: list[type] = []

def _load_xtts(model_name: str) -> TTS:
    """PyTorch 2.6 (weights_only=True) の安全リストを自動追加しながら XTTS をロード"""
    while True:
        try:
            with safe_globals(_ALLOWED):
                return TTS(model_name)
        except Exception as e:
            m = re.search(r"Unsupported global: GLOBAL\s+([\w\.]+)\.([A-Za-z_]\w*)", str(e))
            if not m:
                raise
            mod = importlib.import_module(m.group(1))
            cls = getattr(mod, m.group(2))
            add_safe_globals([cls]); _ALLOWED.append(cls)

MODEL_NAME = os.getenv("TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
VOICE_REFS_DIR = os.getenv("VOICE_REFS_DIR", "/app/refs")
PACKS_ROOT = os.getenv("PACKS_ROOT", "/packs")

# 言語ごとのデフォルト voice_key
DEFAULT_BY_LANG = {"ja": "ja_female_1", "en": "en_female_1", "zh": "zh_female_1"}

# 参照音声レジストリ（環境変数 VOICE_REFS_DIR 基準）
VOICE_REGISTRY = {
    "ja_female_1": {"language": "ja", "speaker_wav": os.path.join(VOICE_REFS_DIR, "alison_ja.wav")},
    "en_female_1": {"language": "en", "speaker_wav": os.path.join(VOICE_REFS_DIR, "alison_en_safe.wav")},
    "zh_female_1": {"language": "zh", "speaker_wav": os.path.join(VOICE_REFS_DIR, "alison_zh.wav")},
}

# グローバルに一度だけロード
_tts = _load_xtts(MODEL_NAME)

def synthesize_and_save(
    *,
    text: str,
    lang: str,
    outfile: str,
    voice_key: Optional[str] = None,
    fmt: str = "mp3",
    bitrate_kbps: int = 64,
) -> str:
    """音声合成して PACKS_ROOT 配下 (or 絶対パス) に保存。返り値は実際の保存パス。"""
    key = voice_key or DEFAULT_BY_LANG.get(lang, "ja_female_1")
    if key not in VOICE_REGISTRY:
        raise ValueError(f"unknown voice_key '{key}'")

    cfg = VOICE_REGISTRY[key]

    # 出力パス（相対なら PACKS_ROOT 配下）
    path = outfile
    if not os.path.isabs(path):
        path = os.path.join(PACKS_ROOT, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # 拡張子をフォーマットに合わせる
    base, _ = os.path.splitext(path)
    path = f"{base}.{fmt}"

    # “バスガイド風” の聞きやすさ向けに、ほんの少しだけ落ち着かせる（任意）
    _tts.tts_to_file(
        text=text,
        language=cfg["language"],
        speaker_wav=cfg["speaker_wav"],
        file_path=path,
        enable_text_splitting=True,
        # 軽微な調整（必要に応じて微調整してOK）
        speed=1.02,         # ほんのわずか速く
        temperature=0.7,    # ランダム性控えめ
    )
    return path

def ensure_packs_root(packs_root: Path) -> None:
    packs_root.mkdir(parents=True, exist_ok=True)

def _map_lang_for_xtts(lang: str) -> str:
    return "zh-cn" if lang == "zh" else lang

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
                mapped = _map_lang_for_xtts(language)
                ref = runtime.cfg.select_voice_ref(language)
                spk = runtime.cfg.select_voice(language)  # REF が無いときの保険
                
                # 参照音声があれば API に渡す（安定）
                api_kwargs: Dict[str, Any] = {"language": mapped}
                if ref:
                    api_kwargs["speaker_wav"] = str(ref)
                elif spk:
                    # 一部のモデルは speaker= を受け付けないため try/except で吸収
                    api_kwargs["speaker"] = spk

                try:
                    runtime._coqui_model.tts_to_file(
                        text=text,
                        file_path=str(out_path),
                        **api_kwargs,
                    )
                except TypeError:
                    # 古いラッパの差異を吸収
                    runtime._coqui_model.tts_to_file(
                        text=text,
                        file_path=str(out_path),
                        language=mapped,
                        **({k: v for k, v in api_kwargs.items() if k in ("speaker_wav","speaker")}),
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
                mapped = _map_lang_for_xtts(language)
                cli_args += ["--language_idx", mapped]
                ref = runtime.cfg.select_voice_ref(language)
                spk = runtime.cfg.select_voice(language)
                if ref:
                    cli_args += ["--speaker_wav", str(ref)]
                elif spk:
                    cli_args += ["--speaker_idx", spk]
                
                lang_arg = "zh-cn" if language == "zh" else language
                cli_args += ["--language_idx", lang_arg]

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
        except (TypeError, ValueError) as e1:
            logger.exception(f"TTS(API) failed. Attempting CLI fallback. Error: {e1}")
            pass

    # 3) フォールバック：簡易WAV（1秒）
    return _sine_wav(duration_sec=1.0, sr=runtime.cfg.sample_rate, freq=440.0)


def shutil_which(name: str) -> Optional[str]:
    from shutil import which
    return which(name)
