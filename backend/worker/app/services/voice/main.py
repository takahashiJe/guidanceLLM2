from __future__ import annotations

import os, json, logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .tts import (
    TTSConfig,
    TTSRuntime,
    ensure_packs_root,
    synthesize_wav_bytes,
    ffmpeg_convert_wav_to_mp3,
    estimate_wav_duration_sec,
    try_ffprobe_duration_sec,
)

logger = logging.getLogger("svc-voice")
logger.setLevel(logging.INFO)

app = FastAPI(title="voice", version="1.0.0")

# ----- 環境設定 -----
PACKS_ROOT = Path(os.getenv("PACKS_ROOT", "/packs"))  # ★ デフォルトを /packs に
DEFAULT_FORMAT = os.getenv("TTS_FORMAT", "mp3").lower()
DEFAULT_BITRATE = int(os.getenv("VOICE_BITRATE_KBPS", "64"))

# 起動前に保存先を用意
ensure_packs_root(PACKS_ROOT)

LANG_MAP = {
    "ja": "ja", "ja-jp": "ja", "ja_jp": "ja",
    "en": "en", "en-us": "en", "en_us": "en", "en-gb": "en", "en_gb": "en",
    "zh": "zh", "zh-cn": "zh", "zh_cn": "zh", "zh-hans": "zh", "zh_hans": "zh",
}

# ----- スキーマ -----
class SingleSynthRequest(BaseModel):
    text: str
    language: Literal["ja", "en", "zh"]
    format: Optional[Literal["mp3", "wav"]] = None
    bitrate_kbps: Optional[int] = None


class SingleSynthResponse(BaseModel):
    # 単発エンドポイントはバイト列は返さず、サイズや推定長だけ返す簡易レスポンス
    size_bytes: int
    duration_sec: float
    format: Literal["mp3", "wav"]


class SynthesizeItem(BaseModel):
    spot_id: str
    text: str


class SynthesizeAndSaveRequest(BaseModel):
    pack_id: str
    language: Literal["ja", "en", "zh"]
    items: List[SynthesizeItem]
    preferred_format: Optional[Literal["mp3", "wav"]] = None
    bitrate_kbps: Optional[int] = None
    save_text: bool = True


class SynthesizeAndSaveItemResponse(BaseModel):
    spot_id: str
    audio_url: str           # ← url ではなく audio_url
    bytes: int               # ← size_bytes ではなく bytes
    duration_s: float        # ← duration_sec ではなく duration_s
    format: Literal["mp3", "wav"]
    text_url: Optional[str] = None


class SynthesizeAndSaveResponse(BaseModel):
    pack_id: str
    language: Literal["ja", "en", "zh"]
    items: List[SynthesizeAndSaveItemResponse]


# ----- ランタイムの初期化（モデルはプロセス内でキャッシュ） -----
_cfg = TTSConfig.from_env()
_runtime = TTSRuntime(_cfg)  # Coqui のモデル等を lazy に握る

def _safe_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # fsync で書き込みを確実化
    with open(path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

def _safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())

def _write_manifest(pack_dir: Path, pack_id: str, language: str, items: list[dict]) -> None:
    manifest_path = pack_dir / "manifest.json"
    payload = {
        "pack_id": pack_id,
        "language": language,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "items": items,  # 返却用と同じ dict リストでOK
    }
    _safe_write_text(manifest_path, json.dumps(payload, ensure_ascii=False, indent=2))

def normalize_lang(s: str) -> str:
    k = s.strip().lower().replace("_", "-")
    return LANG_MAP.get(k, s)

# ----- ヘルスチェック -----
@app.get("/health")
def health():
    return {
        "status": "ok",
        "packs_root": os.getenv("PACKS_ROOT", "/packs"),
        "default_format": "mp3",
        "default_bitrate": 64,
        "model": os.getenv("TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2"),
        "voices": {k: v["language"] for k, v in VOICE_REGISTRY.items()},
        "default_by_lang": DEFAULT_BY_LANG,
    }


# ----- 単発：お試し合成（保存しない） -----
@app.post("/synthesize", response_model=SingleSynthResponse)
def synthesize(req: SingleSynthRequest) -> SingleSynthResponse:
    try:
        wav = synthesize_wav_bytes(runtime=_runtime, text=req.text, language=req.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")

    target_fmt = (req.format or DEFAULT_FORMAT).lower()
    bitrate = int(req.bitrate_kbps or DEFAULT_BITRATE)

    if target_fmt == "mp3":
        try:
            mp3 = ffmpeg_convert_wav_to_mp3(wav, bitrate_kbps=bitrate)
            # 時間は ffprobe があれば使い、無ければビットレート近似
            dur = try_ffprobe_duration_sec(mp3) or max(0.0, len(mp3) * 8.0 / (bitrate * 1000.0))
            return SingleSynthResponse(size_bytes=len(mp3), duration_sec=dur, format="mp3")
        except Exception as e:
            # WAV にフォールバック
            pass

    dur_wav = estimate_wav_duration_sec(wav)
    return SingleSynthResponse(size_bytes=len(wav), duration_sec=dur_wav, format="wav")


# ----- バッチ：保存付き（要求仕様） -----
@app.post("/synthesize_and_save", response_model=SynthesizeAndSaveResponse)
def synthesize_and_save(req: SynthesizeAndSaveRequest) -> SynthesizeAndSaveResponse:
    if not req.items:
        raise HTTPException(status_code=400, detail="items must not be empty")

    pack_dir = PACKS_ROOT / req.pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    target_fmt = (req.preferred_format or DEFAULT_FORMAT).lower()
    bitrate = int(req.bitrate_kbps or DEFAULT_BITRATE)

    out_items: List[SynthesizeAndSaveItemResponse] = []

    for it in req.items:
        # 1) TTS → WAV
        try:
            wav = synthesize_wav_bytes(runtime=_runtime, text=it.text, language=req.language)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS failed for {it.spot_id}: {e}")

        # 2) 変換（mp3優先、失敗時はwavフォールバック）
        fmt = "wav"
        data = wav
        if target_fmt == "mp3":
            try:
                mp3 = ffmpeg_convert_wav_to_mp3(wav, bitrate_kbps=bitrate)
                data = mp3
                fmt = "mp3"
            except Exception:
                fmt = "wav"
                data = wav

        # 3) ファイル名
        audio_name = f"{it.spot_id}.{req.language}.{fmt}"
        text_name  = f"{it.spot_id}.{req.language}.txt"

        # 4) 安全書き込み（fsync）
        try:
            _safe_write_bytes(pack_dir / audio_name, data)
            if req.save_text:
                _safe_write_text(pack_dir / text_name, it.text)
        except Exception as e:
            logger.exception("Failed to write files for %s/%s", req.pack_id, it.spot_id)
            raise HTTPException(status_code=500, detail=f"file write failed: {e}")

        # 5) duration（ffprobe はファイルパスに対して）
        audio_path = pack_dir / audio_name
        if fmt == "wav":
            dur = estimate_wav_duration_sec(data)
        else:
            dur = try_ffprobe_duration_sec(audio_path) or max(0.0, len(data) * 8.0 / (bitrate * 1000.0))

        size = len(data)
        text_url = f"/packs/{req.pack_id}/{text_name}" if req.save_text else None

        # 6) レスポンス item
        out_items.append(
            SynthesizeAndSaveItemResponse(
                spot_id=it.spot_id,
                audio_url=f"/packs/{req.pack_id}/{audio_name}",
                bytes=size,
                duration_s=dur,
                format=fmt,
                text_url=text_url,
            )
        )

        logger.info(
            "Wrote audio: %s (%d bytes, format=%s) text:%s",
            f"/packs/{req.pack_id}/{audio_name}",
            size,
            fmt,
            text_url or "-"
        )

    # 7) manifest をここで確実に保存（return の前）
    _write_manifest(pack_dir, req.pack_id, req.language, [i.model_dump() for i in out_items])

    return SynthesizeAndSaveResponse(
        pack_id=req.pack_id,
        language=req.language,
        items=out_items,
    )


def ensure_pack_dir(pack_id: str) -> Path:
    pack_dir = (PACKS_ROOT / pack_id).resolve()
    # /packs 配下チェック（path traversal 対策）
    if not str(pack_dir).startswith(str(PACKS_ROOT)):
        raise HTTPException(status_code=400, detail="invalid pack_id")
    pack_dir.mkdir(parents=True, exist_ok=True)
    return pack_dir