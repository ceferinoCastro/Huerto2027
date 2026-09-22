from datetime import date, datetime, timezone
import math
import re
import time
from typing import Any
import unicodedata

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request, status
from pymongo.errors import PyMongoError


router = APIRouter(tags=["datos"])

COLLECTION_LIMIT = 100
SUPPORTED_LOCALITIES = {
    "pica",
    "colchane",
    "camina",
    "huara",
    "la-tirana",
    "huayquique",
}

AGRICULTURAL_VARIABLES = (
    "Water Content",
    "Soil Temperature",
    "Matric Potential",
    "Saturation Extract EC",
    "Air Temperature",
    "Relative Humidity",
    "Percent Relative Humidity",
    "Vapor Pressure",
    "VPD",
    "Atmospheric Pressure",
)

INTERNAL_VARIABLES = (
    "Battery Percent",
    "Battery Voltage",
    "Logger Temperature",
    "Reference Pressure",
)

SUMMARY_ITEM_FIELDS = (
    "variable",
    "value",
    "units",
    "datetime",
    "timestamp_utc",
    "sensor_name",
    "sensor_sn",
)


def serialize_mongo(value: Any) -> Any:
    """Recursively convert MongoDB values into JSON-compatible values."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize_mongo(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_mongo(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return value


def normalize_locality(value: str) -> str:
    """Convert a URL locality value into its supported canonical slug."""
    without_accents = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    slug = re.sub(r"[-_\s]+", "-", without_accents.strip().lower())
    if slug not in SUPPORTED_LOCALITIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Localidad no soportada",
        )
    return slug


def variable_sort_key(document: dict[str, Any]) -> tuple[int, int | str]:
    """Put agricultural variables first, then system and unknown variables."""
    variable = document.get("variable")
    if variable in AGRICULTURAL_VARIABLES:
        return 0, AGRICULTURAL_VARIABLES.index(variable)
    if variable in INTERNAL_VARIABLES:
        return 1, INTERNAL_VARIABLES.index(variable)
    return 2, str(variable or "").casefold()


def normalize_summary_item(document: dict[str, Any]) -> dict[str, Any]:
    """Serialize a reading and guarantee the public summary fields."""
    item = serialize_mongo(document)
    for field in SUMMARY_ITEM_FIELDS:
        item.setdefault(field, None)
    return item


def normalize_history_items(
    documents: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Keep numeric measurements and normalize their chart fields."""
    units = next(
        (
            str(document["units"])
            for document in documents
            if document.get("units") is not None
        ),
        None,
    )
    items: list[dict[str, Any]] = []
    for document in documents:
        timestamp = document.get("timestamp_utc")
        value = document.get("value")
        if (
            isinstance(timestamp, bool)
            or not isinstance(timestamp, (int, float))
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            continue

        reading_datetime = document.get("datetime")
        if reading_datetime is None:
            reading_datetime = datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc,
            ).isoformat()
        else:
            reading_datetime = serialize_mongo(reading_datetime)

        items.append(
            {
                "datetime": reading_datetime,
                "timestamp_utc": timestamp,
                "value": value,
            }
        )
    items.sort(key=lambda item: item["timestamp_utc"])
    return units, items


def downsample_lttb(
    items: list[dict[str, Any]],
    threshold: int,
) -> list[dict[str, Any]]:
    """Reduce a numeric time series with Largest-Triangle-Three-Buckets."""
    if threshold >= len(items) or threshold < 3:
        return items.copy()

    sampled = [items[0]]
    bucket_size = (len(items) - 2) / (threshold - 2)
    selected_index = 0

    for bucket in range(threshold - 2):
        average_start = int(math.floor((bucket + 1) * bucket_size)) + 1
        average_end = int(math.floor((bucket + 2) * bucket_size)) + 1
        average_end = min(average_end, len(items))
        average_bucket = items[average_start:average_end] or [items[-1]]
        average_x = sum(
            float(point["timestamp_utc"]) for point in average_bucket
        ) / len(average_bucket)
        average_y = sum(float(point["value"]) for point in average_bucket) / len(
            average_bucket
        )

        range_start = int(math.floor(bucket * bucket_size)) + 1
        range_end = int(math.floor((bucket + 1) * bucket_size)) + 1
        range_end = min(range_end, len(items) - 1)
        point_a = items[selected_index]
        max_area = -1.0
        next_index = range_start

        for candidate_index in range(range_start, range_end):
            candidate = items[candidate_index]
            area = abs(
                (float(point_a["timestamp_utc"]) - average_x)
                * (float(candidate["value"]) - float(point_a["value"]))
                - (
                    float(point_a["timestamp_utc"])
                    - float(candidate["timestamp_utc"])
                )
                * (average_y - float(point_a["value"]))
            )
            if area > max_area:
                max_area = area
                next_index = candidate_index

        sampled.append(items[next_index])
        selected_index = next_index

    sampled.append(items[-1])
    return sampled


def smooth_moving_average(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Smooth interior values with a three-point moving average."""
    if len(items) < 3:
        return [item.copy() for item in items]

    smoothed = [item.copy() for item in items]
    for index in range(1, len(items) - 1):
        smoothed[index]["value"] = sum(
            float(items[position]["value"])
            for position in (index - 1, index, index + 1)
        ) / 3
    return smoothed


async def collection_documents(
    request: Request,
    collection_name: str,
) -> dict[str, Any]:
    try:
        documents = await request.app.state.mongodb.list_documents(
            collection_name,
            limit=COLLECTION_LIMIT,
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc
    items = serialize_mongo(documents)
    return {"status": "ok", "count": len(items), "items": items}


@router.get("/colegios")
async def colegios(request: Request) -> dict[str, Any]:
    return await collection_documents(request, "colegios")


@router.get("/variables")
async def variables(request: Request) -> dict[str, Any]:
    return await collection_documents(request, "variables")


@router.get("/sensores")
async def sensores(request: Request) -> dict[str, Any]:
    return await collection_documents(request, "sensores")


@router.get("/lecturas/ultima")
async def latest_reading(request: Request) -> dict[str, Any]:
    try:
        document = await request.app.state.mongodb.latest_reading()
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc

    item = serialize_mongo(document) if document is not None else None
    return {"status": "ok", "item": item}


@router.get("/localidades/{localidad}/lecturas/ultima")
async def latest_reading_by_locality(
    localidad: str,
    request: Request,
) -> dict[str, Any]:
    normalized_locality = normalize_locality(localidad)
    try:
        document = await request.app.state.mongodb.latest_reading_by_locality(
            normalized_locality
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc

    item = serialize_mongo(document) if document is not None else None
    return {
        "status": "ok",
        "localidad": normalized_locality,
        "item": item,
    }


@router.get("/localidades/{localidad}/lecturas/resumen")
async def latest_readings_summary_by_locality(
    localidad: str,
    request: Request,
) -> dict[str, Any]:
    normalized_locality = normalize_locality(localidad)
    try:
        device_sn, documents = (
            await request.app.state.mongodb.latest_readings_summary_by_locality(
                normalized_locality
            )
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc

    items = [
        normalize_summary_item(document)
        for document in sorted(documents, key=variable_sort_key)
    ]
    return {
        "status": "ok",
        "localidad": normalized_locality,
        "device_sn": device_sn,
        "count": len(items),
        "items": items,
    }


@router.get("/localidades/{localidad}/lecturas/historial")
async def readings_history_by_locality(
    localidad: str,
    request: Request,
    variable: str = Query(min_length=1),
    horas: int = Query(default=24, ge=1, le=720),
    puntos: int = Query(default=60, ge=10, le=300),
    suavizado: bool = True,
) -> dict[str, Any]:
    normalized_locality = normalize_locality(localidad)
    since_timestamp = int(time.time()) - horas * 3600
    try:
        device_sn, documents = (
            await request.app.state.mongodb.readings_history_by_locality(
                normalized_locality,
                variable,
                since_timestamp,
            )
        )
    except (PyMongoError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no está disponible",
        ) from exc

    units, items = normalize_history_items(documents)
    items = downsample_lttb(items, puntos)
    if suavizado:
        items = smooth_moving_average(items)

    return {
        "status": "ok",
        "localidad": normalized_locality,
        "device_sn": device_sn,
        "variable": variable,
        "units": units,
        "range": {"hours": horas, "points_requested": puntos},
        "count": len(items),
        "items": items,
    }
