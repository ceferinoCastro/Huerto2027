from __future__ import annotations

from typing import Any


def carteles_by_key(carteles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Índice clave_educativa -> cartel, resuelve el join en memoria."""
    return {item["clave_educativa"]: item for item in carteles}


def educational_catalog(carteles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expone el catálogo ordenado de carteles tal cual está en Mongo."""
    return [
        {
            "orden": item.get("orden", index),
            "clave_educativa": item["clave_educativa"],
            "nombre_educativo": item["nombre_educativo"],
            "fuente": item.get("fuente_sugerida"),
            "variable_tecnica": item.get("variable_tecnica_sugerida"),
            "sensor_modelo": item.get("sensor_modelo_sugerido"),
            "unidad": item.get("unidad"),
            "categoria": item.get("categoria", ""),
        }
        for index, item in enumerate(carteles, start=1)
    ]


SOURCE_COLLECTIONS = {
    "zentra": "lecturas",
    "hanna": "mediciones_hanna",
    "manual": "mediciones_plantas",
}


def technical_detail(
    variable: str,
    *,
    college_id: str | None,
    catalog: dict[str, dict[str, Any]],
    association: dict[str, Any] | None = None,
    measurement: dict[str, Any] | None = None,
    query_state: str | None = None,
) -> dict[str, Any]:
    definition = catalog.get(variable, {})
    source = (association or {}).get("source") or definition.get("fuente_sugerida")
    technical = (association or {}).get("variable_tecnica") or definition.get("variable_tecnica_sugerida")
    field = "value" if source == "zentra" else technical
    return {
        "clave_educativa": variable,
        "colegio_id": college_id,
        "fuente": source,
        "coleccion": SOURCE_COLLECTIONS.get(source),
        "device_sn": (association or {}).get("device_sn"),
        "sensor_sn": (association or {}).get("sensor_sn"),
        "sensor_modelo": (association or {}).get("sensor_name") or definition.get("sensor_modelo_sugerido"),
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
    catalog: dict[str, dict[str, Any]],
    college_id: str | None = None,
    association: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = catalog.get(variable, {})
    resolved_college_id = college_id or (association or {}).get("colegio_id")
    return {
        "colegio_id": resolved_college_id,
        "localidad": locality,
        "variable": variable,
        "nombre": definition.get("nombre_educativo", variable),
        "valor": None,
        "unidad": definition.get("unidad"),
        "datetime_local": None,
        "fuente": (association or {}).get("source") or definition.get("fuente_sugerida"),
        "estado": state,
        "mensaje": message,
        "detalle_tecnico": technical_detail(
            variable,
            college_id=resolved_college_id,
            catalog=catalog,
            association=association,
            query_state=state,
        ),
    }


def public_measurement(
    association: dict[str, Any],
    measurement: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    definition = catalog.get(association["clave_educativa"], {})
    return {
        "colegio_id": association["colegio_id"],
        "localidad": association["localidad"],
        "variable": association["clave_educativa"],
        "nombre": definition.get("nombre_educativo", association["clave_educativa"]),
        "valor": round(float(measurement["value"]), 4),
        "unidad": measurement.get("units") or definition.get("unidad"),
        "datetime_local": measurement.get("datetime"),
        "timestamp_utc": measurement.get("timestamp_utc"),
        "fuente": association["source"],
        "estado": "ok",
        "detalle_tecnico": technical_detail(
            association["clave_educativa"],
            college_id=association["colegio_id"],
            catalog=catalog,
            association=association,
            measurement=measurement,
            query_state="ok",
        ),
    }
