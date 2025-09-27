# Voice Service (svc-voice) 専用 Dockerfile
# ベースイメージ (共通Dockerfileと同じものを使用)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# Coqui TTSの利用規約同意フラグ（不要になったためコメントアウト）
# ENV COQUI_TOS_AGREED=1

# Voiceサービスに必要なシステム依存 (ffmpeg はgTTSでも利用する可能性があるため残します)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONPATH="/app"

# 1. (ビルドコンテキストのルートから) 共通の requirements.txt をコピーしてインストール
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# 2. (ビルドコンテキストから) Voice専用の requirements.txt をコピーしてインストール
#    （requirements.txt側でCoqui TTS関連がコメントアウトされていることが前提）
COPY backend/worker/app/services/voice/requirements.txt /app/voice_requirements.txt
RUN pip install -r /app/voice_requirements.txt

# 共通Dockerfileに合わせて /packs を作成
RUN mkdir -p /packs && chmod 777 /packs

# PyTorchのUnpicklingError対策パッチ（不要になったためコメントアウト）
# COPY backend/worker/app/services/voice/torch_patch.py /opt/torch_patch.py

EXPOSE 9104