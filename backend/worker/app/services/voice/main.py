# backend/worker/app/services/voice/main.py
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Literal

from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel

# tts.py の公開APIを利用（内部ヘルパの import は最小限に）
from backend.worker.app.services.voice.tts import (
    TTSConfig,
    synthesize as tts_synthesize,
    save_audio,
    _is_wav,                     # 単発エンドポイントでの Content-Type 判定に使用（後方互換）
    _is_mp3,                     # 同上
    _transcode_wav_to_mp3_bytes, # 単発エンドポイントでの簡易トランスコードに使用（任意）
)

app = FastAPI(title="voice-service")

# 保存先（Nginx の /packs に合わせる）
PACKS_DIR = Path(os.getenv("PACKS_DIR", "/packs"))

# =========================
# モデル（/synthesize_and_save 用）
# =========================

class SynthItemIn(BaseModel):
    spot_id: str
    text: str

class SynthItemResult(BaseModel):
    spot_id: str
    url: str
    size_bytes: int
    duration_sec: float
    format: Literal["mp3", "wav"]

class SynthPackRequest(BaseModel):
    pack_id: str
    language: Literal["ja", "en", "zh"]
    items: List[SynthItemIn]
    # 省略時は TTSConfig.format（ENV: TTS_FORMAT）が採用される
    preferred_format: Optional[Literal["mp3", "wav"]] = None

class SynthPackResponse(BaseModel):
    pack_id: str
    language: str
    items: List[SynthItemResult]

# =========================
# モデル（単発 /synthesize 用）
# =========================

class SingleSynthRequest(BaseModel):
    text: str
    language: Literal["ja", "en", "zh"]
    # 省略時は TTSConfig.format（ENV: TTS_FORMAT）が採用される
    format: Optional[Literal["mp3", "wav"]] = None

# =========================
# エンドポイント
# =========================

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/synthesize_and_save", response_model=SynthPackResponse)
def synthesize_and_save(payload: SynthPackRequest):
    """
    複数スポットのテキストを TTS 合成 → /packs/{pack_id}/ に保存して
    URL/サイズ/秒数/フォーマットを返す。
    - Nginx 側で /packs/ を静的配信することで、フロントは Wi-Fi 下で事前DL可能
    """
    cfg = TTSConfig.from_env()
    preferred_fmt = payload.preferred_format or cfg.format

    pack_dir = PACKS_DIR / payload.pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    results: List[SynthItemResult] = []
    for item in payload.items:
        voice_id = cfg.select_voice(payload.language)

        # 音声 bytes 生成（HTTP→ローカル→ダミーの順でフォールバック）
        audio_bytes = tts_synthesize(
            text=item.text,
            language=payload.language,
            voice=voice_id or "",
        )

        # 保存（mp3 指定なら WAV→MP3 変換を試みる。失敗時は WAV 保存にフォールバック）
        url, size_bytes, duration_sec, actual_fmt = save_audio(
            pack_dir=pack_dir,
            spot_id=item.spot_id,
            lang=payload.language,
            data=audio_bytes,
            preferred_format=preferred_fmt,
            bitrate_kbps=64,
        )

        results.append(SynthItemResult(
            spot_id=item.spot_id,
            url=url,
            size_bytes=size_bytes,
            duration_sec=duration_sec,
            format=actual_fmt,
        ))

    return SynthPackResponse(
        pack_id=payload.pack_id,
        language=payload.language,
        items=results,
    )

@app.post("/synthesize")
def synthesize_single(payload: SingleSynthRequest):
    """
    単発の音声を bytes で返す後方互換API。
    - format が mp3 の場合、WAV なら簡易トランスコードを試みる
    - 使い勝手は /synthesize_and_save の方が上（事前配布・キャッシュがしやすい）
    """
    cfg = TTSConfig.from_env()
    target_fmt = payload.format or cfg.format
    voice_id = cfg.select_voice(payload.language)

    audio_bytes = tts_synthesize(
        text=payload.text,
        language=payload.language,
        voice=voice_id or "",
    )

    # 返却フォーマットに合わせる（できる範囲で）
    if target_fmt == "mp3":
        if _is_mp3(audio_bytes):
            return Response(content=audio_bytes, media_type="audio/mpeg")
        if _is_wav(audio_bytes):
            mp3_bytes = _transcode_wav_to_mp3_bytes(audio_bytes, bitrate_kbps=64)
            if mp3_bytes:
                return Response(content=mp3_bytes, media_type="audio/mpeg")
            # 変換失敗時は WAV のまま返却（クライアント側で再生可能ならOK）
            return Response(content=audio_bytes, media_type="audio/wav")
        # 不明形式 → そのまま octet-stream
        return Response(content=audio_bytes, media_type="application/octet-stream")

    # target_fmt == "wav"
    if _is_wav(audio_bytes):
        return Response(content=audio_bytes, media_type="audio/wav")
    # 不明形式 or 既にmp3 など → そのまま返却
    if _is_mp3(audio_bytes):
        return Response(content=audio_bytes, media_type="audio/mpeg")
    return Response(content=audio_bytes, media_type="application/octet-stream")


# ローカルデバッグ用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.worker.app.services.voice.main:app", host="0.0.0.0", port=9104, reload=False)
