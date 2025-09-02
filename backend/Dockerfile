FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VIRTUALENVS_CREATE=false

# 必要に応じてビルド依存を追加
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential netcat-traditional && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update && apt-get install -y --no-install-recommends ffmpeg

WORKDIR /app
ENV PYTHONPATH="/app"

# 依存を先に入れてレイヤを安定化
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt
RUN mkdir -p /packs && chmod 777 /packs

# アプリ本体をコピー
# COPY backend /app/backend
# （workerの地図データなどは volume で供給する想定）

EXPOSE 8080 8090
