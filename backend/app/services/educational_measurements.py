from __future__ import annotations

from typing import Any

from app.services.sensor_associations import EDUCATIONAL_VARIABLES


EDUCATIONAL_NAMES = {
    key: name for key, name, *_rest in EDUCATIONAL_VARIABLES
}
EDUCATIONAL_DEFINITIONS = {
    key: {
        "nombre": name,
        "fuente": source,
        "variable_tecnica": technical,
        "sensor_modelo": sensor_model,
        "unidad": unit,
    }
    for key, name, source, technical, sensor_model, unit, _category in EDUCATIONAL_VARIABLES
}
SOURCE_COLLECTIONS = {
    "zentra": "lecturas",
    "hanna": "mediciones_hanna",
    "manual": "mediciones_plantas",
}


def educational_catalog() -> list[dict[str, Any]]:
    """Expose the ordered educational poster catalog without creating associations."""
    return [
        {
            "orden": order,
            "clave_educativa": key,
            "nombre_educativo": name,
            "fuente": source,
            "variable_tecnica": technical,
            "sensor_modelo": sensor_model,
            "unidad": unit,
            "categoria": category,
        }
        for order, (key, name, source, technical, sensor_model, unit, category)
        in enumerate(EDUCATIONAL_VARIABLES, start=1)
    ]


def technical_detail(
    variable: str,
    *,
    college_id: str | None,
    association: dict[str, Any] | None = None,
    measurement: dict[str, Any] | None = None,
    query_state: str | None = None,
) -> dict[str, Any]:
    definition = EDUCATIONAL_DEFINITIONS.get(variable, {})
    source = (association or {}).get("source") or definition.get("fuente")
    technical = (association or {}).get("variable_tecnica") or definition.get("variable_tecnica")
    field = "value" if source == "zentra" else technical
    return {
        "clave_educativa": variable,
        "colegio_id": college_id,
        "fuente": source,
        "coleccion": SOURCE_COLLECTIONS.get(source),
        "device_sn": (association or {}).get("device_sn"),
        "sensor_sn": (association or {}).get("sensor_sn"),
        "sensor_modelo": (association or {}).get("sensor_name") or definition.get("sensor_modelo"),
        "variable_tecnica": technical,
        "campo_consultado": field,
        "unidad_original": (measurement or {}).get("units"),
        "fecha_original": (measurement or {}).get("datetime"),
        "estado_asociacion": (association or {}).get("estado_asociacion") or (
            "asociada" if association else "sin_asociacion"
        ),
        "serial_hanna": (measurement or {}).get("serial_hanna") or (association or {}).get("sensor_sn") if source == "hanna" else None,
        "modelo": (measurement or {}).get("modelo") or (association or {}).get("sensor_name") if source == "hanna" else None,
        "instrument_id": ((measurement or {}).get("instrument_id") or (association or {}).get("instrument_id")) if source == "hanna" else None,
        "estado": query_state,
    }


def empty_measurement(
    variable: str,
    state: str,
    message: str,
    *,
    locality: str,
    college_id: str | None = None,
    association: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = EDUCATIONAL_DEFINITIONS.get(variable, {})
    resolved_college_id = college_id or (association or {}).get("colegio_id")
    return {
        "colegio_id": resolved_college_id,
        "localidad": locality,
        "variable": variable,
        "nombre": (association or {}).get("nombre_educativo") or EDUCATIONAL_NAMES.get(variable, variable),
        "valor": None,
        "unidad": (association or {}).get("unidad") or definition.get("unidad"),
        "datetime_local": None,
        "fuente": (association or {}).get("source") or definition.get("fuente"),
        "estado": state,
        "mensaje": message,
        "detalle_tecnico": technical_detail(
            variable,
            college_id=resolved_college_id,
            association=association,
            query_state=state,
        ),
    }


def public_measurement(
    association: dict[str, Any],
    measurement: dict[str, Any],
) -> dict[str, Any]:
    result = {
        "colegio_id": association["colegio_id"],
        "localidad": association["localidad"],
        "variable": association["clave_educativa"],
        "nombre": association["nombre_educativo"],
        "valor": round(float(measurement["value"]), 4),
        "unidad": measurement.get("units") or association.get("unidad"),
        "datetime_local": measurement.get("datetime"),
        "timestamp_utc": measurement.get("timestamp_utc"),
        "fuente": association["source"],
        "estado": "ok",
        "detalle_tecnico": technical_detail(
            association["clave_educativa"],
            college_id=association["colegio_id"],
            association=association,
            measurement=measurement,
            query_state="ok",
        ),
    }
    return result
