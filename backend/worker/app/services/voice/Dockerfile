# Voice Service (svc-voice) 専用 Dockerfile
# ベースイメージ (共通Dockerfileと同じものを使用)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

ENV COQUI_TOS_AGREED=1

# Voiceサービスに必要なシステム依存 (ffmpeg のみ)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONPATH="/app"

# 1. (ビルドコンテキストのルートから) 共通の requirements.txt をコピーしてインストール
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# 2. (ビルドコンテキストから) Voice専用の requirements.txt をコピーしてインストール
COPY backend/worker/app/services/voice/requirements.txt /app/voice_requirements.txt
RUN pip install -r /app/voice_requirements.txt

# 共通Dockerfileに合わせて /packs を作成
RUN mkdir -p /packs && chmod 777 /packs
# COPY ./backend/worker/app/services/voice/torch_patch.py /app/backend/worker/app/services/voice/torch_patch.py
COPY backend/worker/app/services/voice/torch_patch.py /opt/torch_patch.py

EXPOSE 9104