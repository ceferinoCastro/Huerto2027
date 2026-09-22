from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.api.routes.read_only import serialize_mongo
from app.models.carteles import CartelInput
from app.services.domain import DomainConflictError, DomainNotFoundError

router = APIRouter(prefix="/carteles", tags=["carteles educativos"])


def _domain_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DomainNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, (DomainConflictError, DuplicateKeyError)):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "MongoDB no está disponible")


@router.get("")
async def list_carteles(request: Request) -> dict[str, Any]:
    try:
        items = await request.app.state.mongodb.list_carteles(force_refresh=True)
    except (PyMongoError, RuntimeError) as exc:
        raise _domain_error(exc) from exc
    serialized = serialize_mongo(items)
    return {"status": "ok", "count": len(serialized), "items": serialized}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_cartel(payload: CartelInput, request: Request) -> dict[str, Any]:
    try:
        item = await request.app.state.mongodb.create_cartel(payload.model_dump())
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError, PyMongoError, RuntimeError) as exc:
        raise _domain_error(exc) from exc
    return serialize_mongo(item)


@router.put("/{clave}")
async def update_cartel(clave: str, payload: CartelInput, request: Request) -> dict[str, Any]:
    if payload.clave_educativa != clave:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La clave educativa del cuerpo no coincide con la de la ruta",
        )
    try:
        item = await request.app.state.mongodb.update_cartel(clave, payload.model_dump())
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError, PyMongoError, RuntimeError) as exc:
        raise _domain_error(exc) from exc
    return serialize_mongo(item)


@router.delete("/{clave}")
async def delete_cartel(clave: str, request: Request) -> dict[str, Any]:
    try:
        await request.app.state.mongodb.delete_cartel(clave)
    except (DomainConflictError, DomainNotFoundError, PyMongoError, RuntimeError) as exc:
        raise _domain_error(exc) from exc
    return {"status": "ok", "deleted": True}
