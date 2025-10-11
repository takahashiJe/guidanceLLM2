from __future__ import annotations

import datetime
import json
import time

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.agent_router import router as agent_router
from backend.api.logging_config import get_device_logger
from backend.api.nav_router import router as nav_router
from backend.api.realtime_router import router as rt_router
from backend.api.routing_router import router as routing_router
from backend.api.user_router import router as user_router


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        device_uuid = request.query_params.get("uuid")
        request_body_bytes = await request.body()
        request_body_for_log = "(no body)"

        if request_body_bytes:
            try:
                request_body_str = request_body_bytes.decode('utf-8')
                request_body_json = json.loads(request_body_str)
                request_body_for_log = json.dumps(request_body_json, indent=2, ensure_ascii=False)
                if not device_uuid and isinstance(request_body_json, dict):
                    device_uuid = request_body_json.get("uuid") or request_body_json.get("thread_id")
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_body_for_log = request_body_bytes.decode(errors='ignore')

        logger = get_device_logger(device_uuid)
        req_log_message = f"[{datetime.datetime.now().isoformat()}] REQUEST: {request.method} {request.url}\n..."
        logger.info(req_log_message)

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        res_body_bytes = b""
        async for chunk in response.body_iterator:
            res_body_bytes += chunk

        try:
            res_body_to_log = json.dumps(json.loads(res_body_bytes.decode('utf-8')), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, UnicodeDecodeError):
            res_body_to_log = res_body_bytes.decode(errors='ignore')

        res_log_message = f"[{datetime.datetime.now().isoformat()}] RESPONSE: {response.status_code} (took {process_time:.4f}s)\nBody: {res_body_to_log}\n---"
        logger.info(res_log_message)

        return Response(content=res_body_bytes, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)

from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway", version="0.1.0")
    # app.add_middleware(LoggingMiddleware) # ログが長すぎるため一時的に無効化

    # origins = [
    #     "https://ibera.cps.akita-pu.ac.jp",
    #     "http://localhost",
    #     "http://localhost:3000",
    #     "http://localhost:5173",
    # ]

    app.add_middleware(
        CORSMiddleware,
        # allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agent_router, prefix="/api")
    app.include_router(user_router, prefix="/api")
    app.include_router(nav_router, prefix="/api")
    app.include_router(rt_router,  prefix="/api")
    app.include_router(routing_router, prefix="/api", tags=["Routing"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()
