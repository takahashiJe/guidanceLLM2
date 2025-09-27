from __future__ import annotations

from fastapi import FastAPI

from backend.api.nav_router import router as nav_router
from backend.api.realtime_router import router as rt_router
from backend.api.routing_router import router as routing_router


def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway", version="0.1.0")

    app.include_router(nav_router, prefix="/api")
    app.include_router(rt_router,  prefix="/api")
    app.include_router(routing_router, prefix="/api", tags=["Routing"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()
