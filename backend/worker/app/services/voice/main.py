from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.worker.app.services.voice import tts

PACKS_DIR = Path(os.getenv("PACKS_DIR", "/packs"))

app = FastAPI(title="voice service")

class SynthesizeRequest(BaseModel):
    language: Literal["ja","en","zh"]
    voice: str
    text: str
    spot_id: str
    pack_id: str

class SynthesizeResponse(BaseModel):
    audio_url: str
    bytes: int
    duration_s: float

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/synthesize", response_model=SynthesizeResponse)
def synthesize(payload: SynthesizeRequest):
    # NOTE: 実処理は tts 側で後ほど実装．ここでは呼び出しだけ行う．
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    data = tts.synthesize(payload.text, payload.language, payload.voice)
    pack_dir = PACKS_DIR / payload.pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    rel_url, nbytes, duration = tts.write_mp3(pack_dir, payload.spot_id, payload.language, data)
    return SynthesizeResponse(audio_url=rel_url, bytes=nbytes, duration_s=duration)
