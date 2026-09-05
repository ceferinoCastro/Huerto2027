from datetime import date, datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from pymongo.errors import PyMongoError

from app.api.routes.read_only import normalize_locality
from app.models.hanna_measurements import (
    HannaImportResponse,
    HannaLatestResponse,
    HannaPreviewResponse,
    HannaSeriesResponse,
    HannaSummaryResponse,
)
from app.services.domain import DomainConflictError, DomainNotFoundError
from app.services.hanna_csv import HannaCSVError, parse_hanna_csv, parse_hanna_metadata


router = APIRouter(prefix="/mediciones-hanna", tags=["mediciones-hanna"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
HANNA_LATEST_VARIABLES = {
    "temperatura": ("temperatura_agua", "Temperatura del agua del estanque", "temp_avg_c", "°C"),
    "temperatura_agua": ("temperatura_agua", "Temperatura del agua del estanque", "temp_avg_c", "°C"),
    "ph": ("ph_agua", "pH del agua", "ph_avg", "pH"),
    "ph_agua": ("ph_agua", "pH del agua", "ph_avg", "pH"),
    "conductividad": ("sales_agua", "Sales del agua", "ec_avg_ms_cm", "mS/cm"),
    "ec": ("sales_agua", "Sales del agua", "ec_avg_ms_cm", "mS/cm"),
    "sales_agua": ("sales_agua", "Sales del agua", "ec_avg_ms_cm", "mS/cm"),
}
HANNA_LATEST_MESSAGES = {
    "sin_equipo_hanna": "Este huerto no tiene un equipo Hanna asociado",
    "sin_datos": "Equipo Hanna asociado, pero sin mediciones cargadas",
    "sin_datos_validos": "No hay una medición válida para esta variable",
}


async def read_upload(archivo: UploadFile) -> tuple[str, bytes]:
    filename = archivo.filename or "archivo.csv"
    if not filename.casefold().endswith(".csv"):
        raise HTTPException(status_code=422, detail="El archivo debe tener extensión .csv")
    content = await archivo.read(MAX_UPLOAD_BYTES + 1)
    await archivo.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el máximo permitido de 25 MB")
    return filename, content


@router.post("/analizar-csv", response_model=HannaPreviewResponse)
async def analyze_hanna_csv(request: Request, archivo: UploadFile = File(...)) -> dict:
    filename, content = await read_upload(archivo)
    try:
        metadata = parse_hanna_metadata(content, filename)
        metadata.pop("header_index", None)
        equipment = await request.app.state.mongodb.hanna_datalogger(metadata["equipo_serial"])
    except HannaCSVError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc
    associated = equipment is not None
    return {
        "archivo_nombre": metadata["archivo_nombre"],
        "modelo": metadata["equipo_modelo"],
        "serial_hanna": metadata["equipo_serial"],
        "instrument_id": metadata["instrument_id"],
        "asociado": associated,
        "equipo": equipment,
        "mensaje": (
            f"Equipo Hanna {metadata['equipo_serial']} reconocido"
            if associated
            else "Este equipo Hanna todavía no está asociado. Seleccione el colegio o huerto al que pertenece."
        ),
    }


@router.post("/importar-csv", response_model=HannaImportResponse)
async def import_hanna_csv(
    request: Request,
    localidad: str | None = Form(default=None),
    colegio_id: str | None = Form(default=None),
    archivo: UploadFile = File(...),
) -> dict:
    filename, content = await read_upload(archivo)
    try:
        parsed = parse_hanna_csv(content, filename)
    except HannaCSVError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    try:
        equipment = await request.app.state.mongodb.hanna_datalogger(parsed["equipo_serial"])
        if equipment is None:
            resolved_college_id = colegio_id
            if resolved_college_id is None and localidad is not None:
                legacy_locality = normalize_locality(localidad)
                college = await request.app.state.mongodb.college_by_locality(legacy_locality)
                resolved_college_id = str(college["_id"]) if college else None
            if resolved_college_id is None:
                raise HTTPException(status_code=409, detail="El equipo Hanna debe asociarse a un colegio antes de importar")
            equipment = await request.app.state.mongodb.associate_hanna_datalogger({
                "serial_hanna": parsed["equipo_serial"],
                "modelo": parsed["equipo_modelo"] or "HI981420",
                "instrument_id": parsed["instrument_id"],
                "colegio_id": resolved_college_id,
                "fecha_asignacion": date.today(),
            })
    except (DomainConflictError, DomainNotFoundError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible") from exc
    locality_value = equipment.get("localidad")
    if not locality_value:
        raise HTTPException(status_code=409, detail="El colegio asociado no tiene una localidad reconocible")
    locality = normalize_locality(locality_value)
    now = datetime.now(timezone.utc)
    documents = [
        {
            "localidad": locality,
            "colegio_id": equipment["colegio_id"],
            "fuente": "hanna_hi981420",
            "archivo_nombre": parsed["archivo_nombre"],
            "equipo_modelo": parsed["equipo_modelo"],
            "equipo_serial": parsed["equipo_serial"],
            "serial_hanna": parsed["equipo_serial"],
            "instrument_id": parsed["instrument_id"],
            **measurement,
            "updated_at": now,
        }
        for measurement in parsed["mediciones"]
    ]
    try:
        result = await request.app.state.mongodb.upsert_hanna_measurements(
            documents
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc

    valid_count = sum(document["valido"] for document in documents)
    return {
        "ok": True,
        "localidad": locality,
        "archivo_nombre": parsed["archivo_nombre"],
        "equipo_modelo": parsed["equipo_modelo"],
        "equipo_serial": parsed["equipo_serial"],
        "instrument_id": parsed["instrument_id"],
        "fecha_inicio": parsed["fecha_inicio"],
        "fecha_fin": parsed["fecha_fin"],
        "registros_leidos": len(documents),
        "insertados": result["created"],
        "actualizados": result["updated"],
        "duplicados": result["updated"],
        "validos": valid_count,
        "invalidos": len(documents) - valid_count,
        "variables_detectadas": parsed["variables_detectadas"],
    }


@router.get("/resumen", response_model=HannaSummaryResponse)
async def hanna_summary(request: Request, localidad: str) -> dict:
    locality = normalize_locality(localidad)
    try:
        assigned, registered = await request.app.state.mongodb.hanna_scope_for_locality(locality)
        summary = await request.app.state.mongodb.hanna_measurements_summary(
            locality, assigned, registered
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc
    return {"localidad": locality, **(summary or {})}


@router.get("/series", response_model=HannaSeriesResponse)
async def hanna_series(
    request: Request,
    localidad: str,
    variable: str,
    dias: int = Query(default=7, ge=1, le=365),
) -> dict:
    locality = normalize_locality(localidad)
    if variable.casefold() != "temperatura":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Por ahora variable debe ser temperatura",
        )
    try:
        assigned, registered = await request.app.state.mongodb.hanna_scope_for_locality(locality)
        documents = await request.app.state.mongodb.hanna_daily_temperature_series(
            locality,
            dias,
            assigned,
            registered,
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc
    items = [
        {"fecha": document["fecha"], "valor": round(float(document["valor"]), 2)}
        for document in documents
    ]
    return {
        "localidad": locality,
        "variable": "temperatura_agua",
        "nombre": "Temperatura del agua del estanque",
        "unidad": "°C",
        "items": items,
    }


@router.get("/ultima", response_model=HannaLatestResponse)
async def latest_hanna_measurement(
    request: Request,
    localidad: str,
    variable: str,
) -> dict:
    locality = normalize_locality(localidad)
    configuration = HANNA_LATEST_VARIABLES.get(variable.casefold())
    if configuration is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="variable debe ser temperatura, ph o conductividad",
        )
    educational_key, name, field, unit = configuration
    try:
        college = await request.app.state.mongodb.college_by_locality(locality)
        college_id = str(
            college.get("colegio_id") or college.get("id") or college.get("_id")
        ) if college else None
        resolved = (
            await request.app.state.mongodb.latest_hanna_field_for_college(college_id, field)
            if college_id
            else {"estado": "sin_equipo_hanna", "documento": None}
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc
    response = {
        "colegio_id": college_id,
        "localidad": locality,
        "variable": educational_key,
        "nombre": name,
        "valor": None,
        "unidad": unit,
        "fecha": None,
        "hora": None,
        "datetime_local": None,
        "fuente": "hanna",
        "serial_hanna": resolved.get("serial_hanna"),
        "modelo": resolved.get("modelo"),
        "instrument_id": resolved.get("instrument_id"),
        "estado": resolved["estado"],
    }
    document = resolved.get("documento")
    if resolved["estado"] != "ok" or document is None:
        return {
            **response,
            "mensaje": HANNA_LATEST_MESSAGES[resolved["estado"]],
        }
    return {
        **response,
        "valor": round(float(document[field]), 2),
        "fecha": document.get("fecha"),
        "hora": document.get("hora"),
        "datetime_local": document.get("datetime_local"),
    }
