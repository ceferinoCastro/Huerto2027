from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from pymongo.errors import PyMongoError

from app.api.routes.read_only import normalize_locality
from app.models.plant_measurements import (
    DailyPlantAveragesResponse,
    DailyPlantMeasurementsInput,
    DailyPlantMeasurementsResponse,
)


router = APIRouter(prefix="/mediciones-plantas", tags=["mediciones-plantas"])


@router.post("", status_code=status.HTTP_200_OK)
async def save_daily_plant_measurements(
    payload: DailyPlantMeasurementsInput,
    request: Request,
) -> dict:
    locality = normalize_locality(payload.localidad)
    now = datetime.now(timezone.utc)
    documents = [
        {
            "localidad": locality,
            "colegio_id": payload.colegio_id,
            "huerto_id": payload.huerto_id,
            "ciclo_id": payload.ciclo_id,
            "fecha": payload.fecha.isoformat(),
            "planta_numero": measurement.planta_numero,
            "altura_cm": measurement.altura_cm,
            "observacion": payload.observacion or "",
            "updated_at": now,
        }
        for measurement in payload.mediciones
    ]
    try:
        result = await request.app.state.mongodb.upsert_plant_measurements(
            documents
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc

    return {
        "status": "ok",
        "localidad": locality,
        "fecha": payload.fecha.isoformat(),
        "ciclo_id": payload.ciclo_id,
        "count": len(documents),
        "created": result["created"],
        "updated": result["updated"],
    }


@router.get("", response_model=DailyPlantMeasurementsResponse)
async def plant_measurements_by_date(
    request: Request,
    localidad: str,
    fecha: str,
    ciclo_id: str = Query(default="general", min_length=1),
) -> dict:
    locality = normalize_locality(localidad)
    try:
        parsed_date = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="fecha debe usar el formato YYYY-MM-DD",
        ) from exc
    try:
        documents = await request.app.state.mongodb.plant_measurements_by_date(
            locality,
            parsed_date.isoformat(),
            ciclo_id,
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc

    items = [
        {
            "planta_numero": document["planta_numero"],
            "altura_cm": document["altura_cm"],
            "observacion": document.get("observacion", ""),
        }
        for document in documents
    ]
    return {
        "status": "ok",
        "localidad": locality,
        "fecha": parsed_date.isoformat(),
        "ciclo_id": ciclo_id,
        "count": len(items),
        "items": items,
    }


@router.get("/promedio", response_model=DailyPlantAveragesResponse)
async def daily_plant_averages(
    request: Request,
    localidad: str,
    dias: int = Query(default=30, ge=1, le=365),
) -> dict:
    locality = normalize_locality(localidad)
    today = datetime.now(timezone.utc).date()
    since_date = (today - timedelta(days=dias - 1)).isoformat()
    try:
        documents = await request.app.state.mongodb.plant_measurement_averages(
            locality,
            since_date,
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc

    items = [
        {
            "fecha": document["fecha"],
            "altura_promedio_cm": round(
                float(document["altura_promedio_cm"]),
                2,
            ),
            "plantas_medidas": int(document["plantas_medidas"]),
        }
        for document in documents
    ]
    return {"localidad": locality, "count": len(items), "items": items}
