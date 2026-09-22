import asyncio
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.api.routes.read_only import downsample_lttb, normalize_locality, serialize_mongo
from app.services.domain import DomainNotFoundError
from app.services.educational_measurements import (
    carteles_by_key,
    educational_catalog,
    empty_measurement,
    public_measurement,
)


router = APIRouter(
    prefix="/localidades/{localidad}/variables-educativas",
    tags=["variables educativas"],
)
LOCAL_TIMEZONE = ZoneInfo("America/Santiago")
HANNA_EMPTY_MESSAGES = {
    "sin_equipo_hanna": "Este huerto no tiene un equipo Hanna asociado",
    "sin_datos": "Equipo Hanna asociado, pero sin mediciones cargadas",
    "sin_datos_validos": "No hay una medición válida para esta variable",
}


def _service_unavailable(variable: str, locality: str, catalog: dict[str, dict[str, Any]]) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=empty_measurement(
            variable,
            "no_disponible",
            "No fue posible consultar esta medición",
            locality=locality,
            catalog=catalog,
        ),
    )


async def _latest(
    request: Request,
    locality: str,
    variable: str,
    catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    college = await request.app.state.mongodb.college_by_locality(locality)
    college_id = str(
        college.get("colegio_id") or college.get("id") or college.get("_id")
    ) if college else None
    definition = catalog.get(variable, {})
    if definition.get("fuente_sugerida") == "hanna":
        if college_id is None:
            return empty_measurement(
                variable,
                "sin_equipo_hanna",
                HANNA_EMPTY_MESSAGES["sin_equipo_hanna"],
                locality=locality,
                catalog=catalog,
            )
        resolved = await request.app.state.mongodb.latest_hanna_field_for_college(
            college_id, definition["variable_tecnica_sugerida"]
        )
        association = {
            "colegio_id": college_id,
            "localidad": locality,
            "clave_educativa": variable,
            "source": "hanna",
            "device_sn": None,
            "sensor_sn": resolved.get("serial_hanna"),
            "sensor_name": resolved.get("modelo") or definition.get("sensor_modelo_sugerido"),
            "instrument_id": resolved.get("instrument_id"),
            "variable_tecnica": definition["variable_tecnica_sugerida"],
            "estado_asociacion": "automatica_hanna",
        }
        if resolved["estado"] != "ok":
            return empty_measurement(
                variable,
                resolved["estado"],
                HANNA_EMPTY_MESSAGES[resolved["estado"]],
                locality=locality,
                catalog=catalog,
                association=association,
            )
        document = resolved["documento"]
        measurement = {
            "value": document[definition["variable_tecnica_sugerida"]],
            "units": definition.get("unidad"),
            "datetime": document.get("datetime_local"),
            "serial_hanna": resolved.get("serial_hanna"),
            "modelo": resolved.get("modelo"),
            "instrument_id": resolved.get("instrument_id"),
        }
        return public_measurement(association, measurement, catalog)

    association = await request.app.state.mongodb.sensor_association(locality, variable)
    if association is None:
        return empty_measurement(
            variable,
            "sin_asociacion",
            "Variable sin sensor asociado",
            locality=locality,
            catalog=catalog,
            college_id=college_id,
        )
    measurement = await request.app.state.mongodb.latest_associated_measurement(association)
    if measurement is None:
        message = (
            "Aún no hay mediciones de planta"
            if association.get("source") == "manual"
            else "Sensor asociado, pero sin mediciones"
        )
        return empty_measurement(
            variable,
            "sin_datos",
            message,
            locality=locality,
            catalog=catalog,
            association=association,
        )
    return public_measurement(association, measurement, catalog)


@router.get("/ultima")
async def latest_educational_summary(
    localidad: str,
    request: Request,
) -> Any:
    locality = normalize_locality(localidad)
    try:
        carteles = await request.app.state.mongodb.list_carteles()
        catalog = carteles_by_key(carteles)
        variables = [
            item["clave_educativa"] for item in carteles
            if item.get("visible_frontend", True) is not False
        ]
        items = await asyncio.gather(*(
            _latest(request, locality, variable, catalog)
            for variable in variables
        ))
    except (PyMongoError, RuntimeError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "localidad": locality,
                "estado": "no_disponible",
                "mensaje": "No fue posible consultar las mediciones",
                "catalogo": [],
                "items": [],
            },
        )
    return {
        "localidad": locality,
        "count": len(items),
        "catalogo": educational_catalog(carteles),
        "items": serialize_mongo(items),
    }


@router.get("/{variable}/ultima")
async def latest_educational_measurement(
    localidad: str,
    variable: str,
    request: Request,
) -> Any:
    locality = normalize_locality(localidad)
    try:
        catalog = carteles_by_key(await request.app.state.mongodb.list_carteles())
    except (PyMongoError, RuntimeError):
        return _service_unavailable(variable, locality, {})
    if variable not in catalog:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variable educativa no soportada")
    try:
        return serialize_mongo(await _latest(request, locality, variable, catalog))
    except (PyMongoError, RuntimeError):
        return _service_unavailable(variable, locality, catalog)


def _parse_boundary(value: str, *, end: bool) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Las fechas deben usar formato ISO YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS",
        ) from exc
    if parsed.tzinfo is None:
        if len(value) == 10:
            parsed = datetime.combine(parsed.date(), time.max if end else time.min)
        parsed = parsed.replace(tzinfo=LOCAL_TIMEZONE)
    return parsed


@router.get("/{variable}/historial")
async def educational_measurement_history(
    localidad: str,
    variable: str,
    request: Request,
    horas: int = Query(default=168, ge=1, le=24 * 365 * 5),
    puntos: int = Query(default=60, ge=10, le=300),
    desde: str | None = None,
    hasta: str | None = None,
    campania_id: str | None = None,
) -> Any:
    locality = normalize_locality(localidad)
    try:
        catalog = carteles_by_key(await request.app.state.mongodb.list_carteles())
    except (PyMongoError, RuntimeError):
        response = empty_measurement(
            variable, "no_disponible", "No fue posible consultar esta medición",
            locality=locality, catalog={},
        )
        response["items"] = []
        return JSONResponse(status_code=503, content=response)
    if variable not in catalog:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variable educativa no soportada")
    try:
        association = await request.app.state.mongodb.sensor_association(locality, variable)
        if association is None:
            return {
                **empty_measurement(
                    variable,
                    "sin_asociacion",
                    "Esta variable aún no tiene un sensor asociado",
                    locality=locality,
                    catalog=catalog,
                ),
                "items": [],
            }
        end_at = datetime.now(timezone.utc)
        start_at = end_at - timedelta(hours=horas)
        if campania_id:
            try:
                period = await request.app.state.mongodb.campaign_period(
                    campania_id, association["colegio_id"]
                )
            except DomainNotFoundError as exc:
                raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
            start_at = _parse_boundary(period["desde"], end=False)
            end_at = _parse_boundary(period["hasta"], end=True)
        else:
            if desde:
                start_at = _parse_boundary(desde, end=False)
            if hasta:
                end_at = _parse_boundary(hasta, end=True)
            if not desde and not hasta:
                latest = await request.app.state.mongodb.latest_associated_measurement(
                    association
                )
                latest_timestamp = (latest or {}).get("timestamp_utc")
                if latest_timestamp is not None:
                    end_at = datetime.fromtimestamp(latest_timestamp, timezone.utc)
                    start_at = end_at - timedelta(hours=horas)
        if end_at < start_at:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "hasta no puede ser anterior a desde",
            )
        documents = await request.app.state.mongodb.associated_measurement_series(
            association,
            int(start_at.timestamp()),
            int(end_at.timestamp()),
        )
    except HTTPException:
        raise
    except (PyMongoError, RuntimeError):
        response = empty_measurement(
            variable,
            "no_disponible",
            "No fue posible consultar esta medición",
            locality=locality,
            catalog=catalog,
        )
        response["items"] = []
        return JSONResponse(status_code=503, content=response)
    normalized = [
        {
            "datetime": item.get("datetime"),
            "timestamp_utc": item.get("timestamp_utc"),
            "value": round(float(item["value"]), 4),
            **({"plantas_medidas": item["plantas_medidas"]} if item.get("plantas_medidas") is not None else {}),
        }
        for item in documents
    ]
    normalized.sort(key=lambda item: item.get("timestamp_utc") or 0)
    normalized = downsample_lttb(normalized, puntos)
    state = "ok" if normalized else "sin_datos"
    return {
        "colegio_id": association["colegio_id"],
        "localidad": locality,
        "variable": variable,
        "nombre": catalog.get(variable, {}).get("nombre_educativo", variable),
        "unidad": catalog.get(variable, {}).get("unidad"),
        "fuente": association["source"],
        "estado": state,
        "mensaje": None if normalized else "El sensor asociado aún no tiene mediciones en este periodo",
        "periodo": {
            "desde": start_at.isoformat(),
            "hasta": end_at.isoformat(),
            "campania_id": campania_id,
        },
        "count": len(normalized),
        "items": serialize_mongo(normalized),
    }
