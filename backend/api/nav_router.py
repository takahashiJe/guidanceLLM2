
from __future__ import annotations

import os
import uuid
import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from backend.api.schemas import PlanRequest, PlanResponse

router = APIRouter(prefix="/nav", tags=["navigation"])

# The new NAV service is running as a separate service.
NAV_BASE = os.getenv("NAV_BASE", "http://svc-nav:9100")
REQ_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "300"))

def _request_id(headers) -> str:
    return headers.get("x-request-id") or str(uuid.uuid4())

@router.post("/plan", response_model=PlanResponse, status_code=status.HTTP_200_OK)
def create_nav_plan(req: PlanRequest, request: Request):
    """
    Accepts a navigation plan request, forwards it to the synchronous Nav service,
    and returns the complete plan.
    """
    headers = {"x-request-id": _request_id(request.headers)}
    
    # The request to the nav service is now a direct HTTP call.
    # The polling mechanism is no longer needed.
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{NAV_BASE}/plan",
                json=req.model_dump(by_alias=True),
                headers=headers,
                timeout=REQ_TIMEOUT,
            )
            response.raise_for_status() # Raise an exception for 4xx or 5xx status codes
            
            # The nav service now returns the final PlanResponse directly.
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=response.json(),
            )

    except httpx.RequestError as e:
        # Error connecting to the nav service
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Nav service is unavailable: {e}"
        )
    except httpx.HTTPStatusError as e:
        # Error response from the nav service
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error from nav service: {e.response.text}"
        )
