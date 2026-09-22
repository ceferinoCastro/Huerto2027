from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.api.routes.read_only import normalize_locality, serialize_mongo
from app.models.sensor_associations import SensorAssociationInput
from app.services.domain import DomainConflictError, DomainNotFoundError


router = APIRouter(prefix="/asociaciones-sensores", tags=["asociaciones sensores"])


def _domain_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DomainNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, (DomainConflictError, DuplicateKeyError)):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"MongoDB no está disponible: {exc}")
    if isinstance(exc, PyMongoError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"MongoDB no está disponible: {exc}")
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Error inesperado al procesar la asociación: {exc}")


@router.get("")
async def list_associations(request: Request, localidad: str = Query(min_length=1)) -> dict[str, Any]:
    normalized = normalize_locality(localidad)
    try:
        items = await request.app.state.mongodb.list_sensor_associations(normalized)
    except (PyMongoError, RuntimeError) as exc:
        print(f"Error al listar asociaciones: {exc}")
        raise _domain_error(exc) from exc
    serialized = serialize_mongo(items)
    return {"status": "ok", "count": len(serialized), "items": serialized}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_association(payload: SensorAssociationInput, request: Request) -> dict[str, Any]:
    try:
        item = await request.app.state.mongodb.create_sensor_association(payload.model_dump())
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError, PyMongoError, RuntimeError) as exc:
        print(f"Error al guardar asociación: {exc}")
        raise _domain_error(exc) from exc
    except Exception as exc:
        print(f"Error inesperado al guardar asociación: {exc}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Error inesperado al guardar la asociación: {exc}",
        ) from exc
    return serialize_mongo(item)


@router.put("/{association_id}")
async def update_association(association_id: str, payload: SensorAssociationInput, request: Request) -> dict[str, Any]:
    try:
        item = await request.app.state.mongodb.update_sensor_association(association_id, payload.model_dump())
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError, PyMongoError, RuntimeError) as exc:
        print(f"Error al actualizar asociación: {exc}")
        raise _domain_error(exc) from exc
    except Exception as exc:
        print(f"Error inesperado al actualizar asociación: {exc}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Error inesperado al actualizar la asociación: {exc}",
        ) from exc
    return serialize_mongo(item)


@router.delete("/{association_id}")
async def delete_association(association_id: str, request: Request) -> dict[str, Any]:
    try:
        await request.app.state.mongodb.delete_sensor_association(association_id)
    except (DomainNotFoundError, PyMongoError, RuntimeError) as exc:
        print(f"Error al eliminar asociación: {exc}")
        raise _domain_error(exc) from exc
    return {"status": "ok", "deleted": True}
