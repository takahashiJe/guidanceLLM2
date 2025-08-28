from __future__ import annotations

from fastapi import FastAPI

from backend.api.nav_router import router as nav_router


def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway", version="0.1.0")

    # 将来のAIエージェント系は別routerに切り出してここで include する想定
    app.include_router(nav_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


# Uvicorn 実行ポイント（例: uvicorn backend.api.main:app --host 0.0.0.0 --port 8000）
app = create_app()
