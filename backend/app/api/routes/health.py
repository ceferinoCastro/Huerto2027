from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo.errors import PyMongoError


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    mongodb: Literal["connected", "unavailable"]


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(request: Request) -> HealthResponse | JSONResponse:
    """Report API and MongoDB availability without changing database data."""
    try:
        await request.app.state.mongodb.ping()
    except (PyMongoError, RuntimeError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "mongodb": "unavailable"},
        )

    return HealthResponse(status="ok", mongodb="connected")
