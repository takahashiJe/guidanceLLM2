from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="llm service")

@app.get("/health")
def health():
    return {"status": "ok"}