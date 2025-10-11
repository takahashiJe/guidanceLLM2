

from __future__ import annotations

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json
import datetime
import time

from backend.api.logging_config import get_device_logger
from backend.api.nav_router import router as nav_router
from backend.api.realtime_router import router as rt_router
from backend.api.routing_router import router as routing_router


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Extract UUID from query parameters (for GET requests) or body (for POST)
        device_uuid = request.query_params.get("uuid")

        request_body_bytes = await request.body()
        request_body_for_log = "(no body)"

        if request_body_bytes:
            try:
                request_body_str = request_body_bytes.decode('utf-8')
                request_body_json = json.loads(request_body_str)
                request_body_for_log = json.dumps(request_body_json, indent=2, ensure_ascii=False)

                # Extract UUID from JSON body if not found in query params
                if not device_uuid and isinstance(request_body_json, dict):
                    device_uuid = request_body_json.get("uuid")
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_body_for_log = request_body_bytes.decode(errors='ignore')

        logger = get_device_logger(device_uuid)

        # 2. Log Request Details
        req_log_message = (
            f"[{datetime.datetime.now().isoformat()}] REQUEST: {request.method} {request.url}\n"
            f"Headers: {dict(request.headers)}\n"
            f"Body: {request_body_for_log}\n"
            "---"
        )
        logger.info(req_log_message)

        # 3. Process Request and Get Response
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        # 4. Log Response Details
        res_body_bytes = b""
        async for chunk in response.body_iterator:
            res_body_bytes += chunk

        try:
            # Try to format as pretty JSON if possible
            res_body_json = json.loads(res_body_bytes.decode('utf-8'))
            res_body_to_log = json.dumps(res_body_json, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, UnicodeDecodeError):
            res_body_to_log = res_body_bytes.decode(errors='ignore')

        res_log_message = (
            f"[{datetime.datetime.now().isoformat()}] RESPONSE: {response.status_code} (took {process_time:.4f}s)\n"
            f"Body: {res_body_to_log}\n"
            "----------------------------------------"
        )
        logger.info(res_log_message)

        # 5. Return a new response with the consumed body
        return Response(
            content=res_body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway", version="0.1.0")

    # Add the logging middleware
    app.add_middleware(LoggingMiddleware)

    app.include_router(nav_router, prefix="/api")
    app.include_router(rt_router,  prefix="/api")
    app.include_router(routing_router, prefix="/api", tags=["Routing"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()
