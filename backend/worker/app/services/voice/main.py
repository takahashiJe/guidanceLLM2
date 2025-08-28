from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.worker.app.services.voice import tts

app = FastAPI(title="voice service")

class SynthesizeRequest(BaseModel):
    language: Literal["ja", "en", "zh"]
    voice: str
    text: str
    spot_id: str
    pack_id: str
    format: Literal["mp3", "wav"] = "mp3"
    bitrate_kbps: int = 64
    save_text: bool = False

class SynthesizeResponse(BaseModel):
    audio_url: str
    bytes: int
    duration_s: float
    format: Literal["mp3", "wav"]
    text_url: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/synthesize", response_model=SynthesizeResponse)
def synthesize(req: SynthesizeRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")
    if not req.pack_id.strip():
        raise HTTPException(status_code=400, detail="pack_id is required")

    # 1) TTS 合成（WAV などのバイト列）
    audio_bytes = tts.synthesize(req.text, req.language, req.voice)

    # 2) 保存ディレクトリ
    base_dir = Path(os.getenv("PACKS_DIR", "/data/packs"))
    pack_dir = base_dir / req.pack_id

    # 3) 希望フォーマットで保存（mp3 推奨、失敗時は WAV にフォールバック）
    audio_url, nbytes, dur, actual_fmt = tts.save_audio(
        pack_dir=pack_dir,
        spot_id=req.spot_id,
        lang=req.language,
        data=audio_bytes,
        preferred_format=req.format,
        bitrate_kbps=req.bitrate_kbps,
    )

    # 4) テキストも保存（任意）
    text_url: Optional[str] = None
    if req.save_text:
        pack_dir.mkdir(parents=True, exist_ok=True)
        text_path = pack_dir / f"{req.spot_id}.{req.language}.txt"
        text_path.write_text(req.text, encoding="utf-8")
        text_url = f"/packs/{req.pack_id}/{req.spot_id}.{req.language}.txt"

    return SynthesizeResponse(
        audio_url=audio_url,
        bytes=nbytes,
        duration_s=dur,
        format=actual_fmt,
        text_url=text_url,
    )
