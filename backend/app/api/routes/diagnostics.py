from typing import Any, Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo.errors import PyMongoError


router = APIRouter(prefix="/diagnostico", tags=["diagnostico"])


class CollectionsResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    collections: list[str]


@router.get(
    "/colecciones",
    response_model=CollectionsResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CollectionsResponse}
    },
)
async def collections(request: Request) -> CollectionsResponse | JSONResponse:
    """List MongoDB collections without reading or changing their documents."""
    try:
        names = await request.app.state.mongodb.list_collection_names()
    except (PyMongoError, RuntimeError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "collections": []},
        )

    return CollectionsResponse(status="ok", collections=sorted(names))


@router.get("/lecturas/rendimiento")
async def readings_performance(request: Request) -> Any:
    """Summarize indexes and execution plans for two read-only queries."""
    try:
        diagnostics = (
            await request.app.state.mongodb.readings_performance_diagnostics()
        )
    except (PyMongoError, RuntimeError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable"},
        )

    return {"status": "ok", "collection": "lecturas", **diagnostics}
