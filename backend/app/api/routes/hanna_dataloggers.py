from fastapi import APIRouter, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.models.hanna_dataloggers import (
    HannaAssociateInput,
    HannaCorrectionInput,
    HannaDataloggerResponse,
    HannaReplacementInput,
)
from app.services.domain import DomainConflictError, DomainNotFoundError


router = APIRouter(prefix="/dataloggers-hanna", tags=["dataloggers-hanna"])


def domain_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DomainNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("")
async def list_hanna_dataloggers(request: Request) -> dict:
    try:
        items = await request.app.state.mongodb.list_hanna_dataloggers()
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc
    return {"count": len(items), "items": items}


@router.post("/asociar", response_model=HannaDataloggerResponse, status_code=201)
async def associate_hanna(payload: HannaAssociateInput, request: Request) -> dict:
    try:
        return await request.app.state.mongodb.associate_hanna_datalogger(payload.model_dump())
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError) as exc:
        raise domain_error(exc) from exc
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc


@router.put("/{serial_hanna}/corregir-asignacion", response_model=HannaDataloggerResponse)
async def correct_hanna_assignment(
    serial_hanna: str, payload: HannaCorrectionInput, request: Request
) -> dict:
    try:
        return await request.app.state.mongodb.correct_hanna_assignment(
            serial_hanna, payload.colegio_id, payload.usuario
        )
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError) as exc:
        raise domain_error(exc) from exc
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc


@router.post("/{serial_hanna}/reemplazar")
async def replace_hanna(
    serial_hanna: str, payload: HannaReplacementInput, request: Request
) -> dict:
    try:
        return await request.app.state.mongodb.replace_hanna_datalogger(
            serial_hanna, payload.model_dump()
        )
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError) as exc:
        raise domain_error(exc) from exc
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc

