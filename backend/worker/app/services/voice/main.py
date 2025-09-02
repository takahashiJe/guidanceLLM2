from __future__ import annotations

import os
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

app = FastAPI(title="voice", version="1.0.0")

# ----- 環境設定 -----
PACKS_ROOT = Path(os.getenv("PACKS_ROOT", "/home/junta_takahashi/guidanceLLM2/packs"))
DEFAULT_FORMAT = os.getenv("TTS_FORMAT", "mp3").lower()
DEFAULT_BITRATE = int(os.getenv("VOICE_BITRATE_KBPS", "64"))

# 起動前に保存先を用意
ensure_packs_root(PACKS_ROOT)


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
    url: str
    size_bytes: int
    duration_sec: float
    format: Literal["mp3", "wav"]
    text_url: Optional[str] = None


class SynthesizeAndSaveResponse(BaseModel):
    pack_id: str
    language: Literal["ja", "en", "zh"]
    items: List[SynthesizeAndSaveItemResponse]


# ----- ランタイムの初期化（モデルはプロセス内でキャッシュ） -----
_cfg = TTSConfig.from_env()
_runtime = TTSRuntime(_cfg)  # Coqui のモデル等を lazy に握る


# ----- ヘルスチェック -----
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "packs_root": str(PACKS_ROOT),
        "default_format": DEFAULT_FORMAT,
        "default_bitrate": DEFAULT_BITRATE,
        "model": _cfg.model_name,
        "voices": {
            "ja": _cfg.voice_ja,
            "en": _cfg.voice_en,
            "zh": _cfg.voice_zh,
        },
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

    # 保存先
    pack_dir = PACKS_ROOT / req.pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    target_fmt = (req.preferred_format or DEFAULT_FORMAT).lower()
    bitrate = int(req.bitrate_kbps or DEFAULT_BITRATE)

    out_items: List[SynthesizeAndSaveItemResponse] = []

    # 1件ずつ合成・変換・保存
    for it in req.items:
        try:
            wav = synthesize_wav_bytes(runtime=_runtime, text=it.text, language=req.language)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS failed for {it.spot_id}: {e}")

        fmt = "wav"
        data = wav

        if target_fmt == "mp3":
            try:
                mp3 = ffmpeg_convert_wav_to_mp3(wav, bitrate_kbps=bitrate)
                data = mp3
                fmt = "mp3"
            except Exception:
                # フォールバック（WAV のまま）
                fmt = "wav"
                data = wav

        # ファイル名 & 保存
        audio_name = f"{it.spot_id}.{req.language}.{fmt}"
        (pack_dir / audio_name).write_bytes(data)

        # duration
        if fmt == "wav":
            dur = estimate_wav_duration_sec(data)
        else:
            dur = try_ffprobe_duration_sec(data) or max(0.0, len(data) * 8.0 / (bitrate * 1000.0))

        text_url: Optional[str] = None
        if req.save_text:
            txt_name = f"{it.spot_id}.{req.language}.txt"
            (pack_dir / txt_name).write_text(it.text, encoding="utf-8")
            text_url = f"/packs/{req.pack_id}/{txt_name}"

        out_items.append(
            SynthesizeAndSaveItemResponse(
                spot_id=it.spot_id,
                url=f"/packs/{req.pack_id}/{audio_name}",
                size_bytes=len(data),
                duration_sec=dur,
                format=fmt,  # "mp3" or "wav"
                text_url=text_url,
            )
        )

    return SynthesizeAndSaveResponse(
        pack_id=req.pack_id,
        language=req.language,
        items=out_items,
    )
