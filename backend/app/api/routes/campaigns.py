from fastapi import APIRouter, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.models.campaigns import (
    CampaignCancelInput,
    CampaignCreateInput,
    CampaignEditInput,
    CampaignFinishInput,
    CampaignReopenInput,
)
from app.services.domain import DomainConflictError, DomainNotFoundError


router = APIRouter(prefix="/campanias", tags=["campanias"])


def raise_domain_error(exc: Exception) -> None:
    code = status.HTTP_404_NOT_FOUND if isinstance(exc, DomainNotFoundError) else status.HTTP_409_CONFLICT
    raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("")
async def list_campaigns(colegio_id: str, request: Request) -> dict:
    try:
        items = await request.app.state.mongodb.campaigns_for_college(colegio_id)
    except DomainNotFoundError as exc:
        raise_domain_error(exc)
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc
    return {"colegio_id": colegio_id, "count": len(items), "items": items}


@router.get("/activa")
async def active_campaign(colegio_id: str, request: Request) -> dict:
    try:
        item = await request.app.state.mongodb.active_campaign(colegio_id)
    except DomainNotFoundError as exc:
        raise_domain_error(exc)
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc
    return {"colegio_id": colegio_id, "item": item}


@router.post("", status_code=201)
async def create_campaign(payload: CampaignCreateInput, request: Request) -> dict:
    try:
        return await request.app.state.mongodb.create_campaign(payload.model_dump())
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError) as exc:
        raise_domain_error(exc)
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc


@router.patch("/{campania_id}")
async def update_campaign(
    campania_id: str, payload: CampaignEditInput, request: Request
) -> dict:
    try:
        return await request.app.state.mongodb.update_campaign(
            campania_id, payload.model_dump(exclude_unset=True, mode="json")
        )
    except (DomainConflictError, DomainNotFoundError) as exc:
        raise_domain_error(exc)
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc


@router.post("/{campania_id}/finalizar")
@router.put("/{campania_id}/finalizar")
async def finish_campaign(
    campania_id: str, payload: CampaignFinishInput, request: Request
) -> dict:
    try:
        return await request.app.state.mongodb.finish_campaign(campania_id, {
            **payload.model_dump(mode="json"),
        })
    except (DomainConflictError, DomainNotFoundError) as exc:
        raise_domain_error(exc)
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc


@router.post("/{campania_id}/cancelar")
@router.put("/{campania_id}/cancelar")
async def cancel_campaign(
    campania_id: str, payload: CampaignCancelInput, request: Request
) -> dict:
    try:
        return await request.app.state.mongodb.cancel_campaign(
            campania_id, payload.model_dump(mode="json")
        )
    except (DomainConflictError, DomainNotFoundError) as exc:
        raise_domain_error(exc)
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc


@router.post("/{campania_id}/reabrir")
async def reopen_campaign(
    campania_id: str, payload: CampaignReopenInput, request: Request
) -> dict:
    try:
        return await request.app.state.mongodb.reopen_campaign(
            campania_id, payload.model_dump(mode="json")
        )
    except (DomainConflictError, DomainNotFoundError, DuplicateKeyError) as exc:
        raise_domain_error(exc)
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc


@router.get("/{campania_id}/historial")
async def campaign_history(campania_id: str, request: Request) -> dict:
    try:
        item = await request.app.state.mongodb.campaign_history(campania_id)
    except (DomainConflictError, DomainNotFoundError) as exc:
        raise_domain_error(exc)
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc
    return {"campania_id": campania_id, "count": len(item), "items": item}
