from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.mongodb import LOCALITY_DEVICE_SN
from app.services.compatibility import locality_from_college, normalize_text


_POSTER_SEED_DEFINITIONS = (
    ("temperatura_aire", "Temperatura del aire", "zentra", "Air Temperature", "ATMOS 14", "°C", "temperatura"),
    ("humedad_aire", "Agua en el aire", "zentra", "Percent Relative Humidity", "ATMOS 14", "%", "humedad"),
    ("humedad_hojas", "Agua en hojas", "zentra", "Leaf Wetness", None, "%", "humedad"),
    ("temperatura_tierra", "Temperatura de la tierra", "zentra", "Soil Temperature", "TEROS 12", "°C", "temperatura"),
    ("temperatura_bajo_tierra", "Temperatura bajo tierra", "zentra", "Soil Temperature", "TEROS 21", "°C", "temperatura"),
    ("humedad_tierra", "Agua en tierra", "zentra", "Water Content", "TEROS 12", "%", "humedad"),
    ("ph_agua", "pH del agua", "hanna", "ph_avg", "HI981420", "pH", "agua"),
    ("sales_agua", "Sales del agua", "hanna", "ec_avg_ms_cm", "HI981420", "mS/cm", "agua"),
    ("temperatura_agua", "Temperatura del agua", "hanna", "temp_avg_c", "HI981420", "°C", "agua"),
    ("altura_planta", "Alto de planta", "manual", "altura_cm", None, "cm", "plantas"),
    ("largo_raiz", "Largo de raíz", "manual", "largo_raiz_cm", None, "cm", "plantas"),
)

# Semilla para migrar los carteles fijos a la colección `carteles_educativos`
# (ver backend/scripts/migrate_educational_posters.py). No se persiste tal
# cual en una asociación — ver _ASSOCIATION_FIELDS para eso.
EDUCATIONAL_POSTER_SEED = [
    {
        "clave_educativa": key,
        "nombre_educativo": label,
        "categoria": category,
        "unidad": unit,
        "orden": order,
        "visible_frontend": True,
        "fuente_sugerida": source,
        "variable_tecnica_sugerida": technical,
        "sensor_modelo_sugerido": sensor_model,
    }
    for order, (key, label, source, technical, sensor_model, unit, category)
    in enumerate(_POSTER_SEED_DEFINITIONS, start=1)
]

# Nombres alternativos que la estación meteorológica puede reportar para la
# misma variable técnica (p. ej. Zentra devuelve "Percent Relative Humidity"
# para el sensor ATMOS 14, pero lecturas históricas usan "Relative Humidity").
_VARIABLE_ALIASES: dict[str, tuple[str, ...]] = {
    "Percent Relative Humidity": ("Relative Humidity",),
}


# Campos de una propuesta que realmente corresponden a una ASOCIACIÓN
# persistible (no al cartel). build_initial_association_proposal() agrega
# además campos de solo-reporte (colegio_nombre, cantidad_lecturas,
# ultima_lectura, confianza, motivo) que upsert_initial_sensor_associations()
# debe descartar antes de escribir a Mongo.
_ASSOCIATION_FIELDS = {
    "localidad", "colegio_id", "clave_educativa", "source", "variable_tecnica",
    "device_sn", "sensor_sn", "sensor_name", "ubicacion", "profundidad_cm",
    "estado_asociacion", "provisional", "origen_asignacion", "created_at", "updated_at",
}


def _catalog_by_serial(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("sensor_sn")): item
        for item in items
        if item.get("sensor_sn")
    }


def _location_confidence(sensor_name: str, location: str | None) -> tuple[str, bool]:
    normalized = normalize_text(location)
    if sensor_name == "TEROS 21" and any(word in normalized for word in ("profund", "raiz")):
        return "alta", False
    if sensor_name == "TEROS 12" and any(word in normalized for word in ("cama", "cantero", "surco", "huerto")):
        return "alta", False
    return "media", True


def build_initial_association_proposal(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a deterministic proposal using only observed database evidence."""
    now = datetime.now(timezone.utc)
    catalog = _catalog_by_serial(inventory.get("sensores", []))
    readings = inventory.get("lecturas", [])
    hanna = inventory.get("hanna", [])
    hanna_assignments = inventory.get("dataloggers_hanna", [])
    locality_devices = dict(LOCALITY_DEVICE_SN)
    locality_devices.update({
        locality_from_college({"nombre": item.get("ubicacion")}): item.get("modelo")
        for item in inventory.get("dataloggers", [])
        if locality_from_college({"nombre": item.get("ubicacion")})
    })
    proposals: list[dict[str, Any]] = []

    for college in inventory.get("colegios", []):
        locality = locality_from_college(college)
        if not locality:
            continue
        college_id = str(college.get("colegio_id") or college.get("id") or college.get("_id"))
        device_sn = locality_devices.get(locality)
        for definition in _POSTER_SEED_DEFINITIONS:
            key, _label, source, technical, sensor_model, expected_unit, _category = definition
            base = {
                "localidad": locality,
                "colegio_id": college_id,
                "colegio_nombre": college.get("nombre", "Colegio sin nombre"),
                "clave_educativa": key,
                "source": source,
                "variable_tecnica": technical,
                "unidad": expected_unit,
                "origen_asignacion": "inicial_automatica",
                "updated_at": now,
            }
            if source == "manual":
                proposals.append({
                    **base,
                    "device_sn": None,
                    "sensor_sn": None,
                    "sensor_name": "Medición manual de plantas",
                    "ubicacion": None,
                    "profundidad_cm": None,
                    "cantidad_lecturas": None,
                    "ultima_lectura": None,
                    "confianza": "alta",
                    "provisional": False,
                    "estado_asociacion": "asociada",
                    "motivo": "Fuente manual existente; no utiliza sensores ni lecturas Zentra/Hanna.",
                })
                continue

            if source == "hanna":
                assigned = [
                    item for item in hanna_assignments
                    if str(item.get("colegio_id")) == college_id
                ]
                serials = {str(item.get("serial_hanna")) for item in assigned}
                candidates = [item for item in hanna if str(item.get("serial_hanna")) in serials]
                candidates.sort(key=lambda item: (item.get("count") or 0, str(item.get("last") or "")), reverse=True)
                if candidates:
                    candidate = candidates[0]
                    proposals.append({
                        **base,
                        "device_sn": None,
                        "sensor_sn": candidate["serial_hanna"],
                        "sensor_name": sensor_model,
                        "cantidad_lecturas": candidate.get("count", 0),
                        "ultima_lectura": candidate.get("last"),
                        "confianza": "alta",
                        "provisional": False,
                        "estado_asociacion": "asociada",
                        "motivo": "Serial Hanna asociado previamente al colegio y campo medido existente.",
                    })
                else:
                    proposals.append({
                        **base,
                        "device_sn": None,
                        "sensor_sn": None,
                        "sensor_name": sensor_model,
                        "cantidad_lecturas": 0,
                        "ultima_lectura": None,
                        "confianza": "pendiente",
                        "provisional": False,
                        "estado_asociacion": "pendiente",
                        "motivo": "El colegio no tiene un equipo Hanna asociado previamente.",
                    })
                continue

            accepted_variables = {technical, *_VARIABLE_ALIASES.get(technical, ())}
            candidates = [
                item for item in readings
                if item.get("device_sn") == device_sn
                and item.get("variable") in accepted_variables
                and item.get("sensor_sn")
                and (sensor_model is None or item.get("sensor_name") == sensor_model)
                and (item.get("count") or 0) > 0
            ]
            candidates.sort(
                key=lambda item: (
                    item.get("count") or 0,
                    item.get("last_ts") or 0,
                    str(item.get("sensor_sn") or ""),
                ),
                reverse=True,
            )
            if not candidates:
                proposals.append({
                    **base,
                    "device_sn": device_sn,
                    "sensor_sn": None,
                    "sensor_name": sensor_model,
                    "cantidad_lecturas": 0,
                    "ultima_lectura": None,
                    "confianza": "pendiente",
                    "provisional": False,
                    "estado_asociacion": "pendiente",
                    "motivo": f"No existen lecturas reales de {technical} para el datalogger del colegio.",
                })
                continue

            candidate = candidates[0]
            sensor = catalog.get(str(candidate["sensor_sn"]), {})
            location = sensor.get("ubicacion_fisica")
            confidence, provisional = "alta", False
            reason = "Canal técnico exacto con lecturas numéricas reales."
            if key in {"temperatura_tierra", "temperatura_bajo_tierra"}:
                confidence, provisional = _location_confidence(str(candidate.get("sensor_name")), location)
                if provisional:
                    reason = "Sensor TEROS diferenciado y con lecturas reales, pero sin ubicación/profundidad registrada; asociación provisional."
            proposals.append({
                **base,
                "device_sn": device_sn,
                "sensor_sn": candidate["sensor_sn"],
                "sensor_name": candidate.get("sensor_name"),
                "unidad": candidate.get("units") or expected_unit,
                "ubicacion": location,
                "profundidad_cm": sensor.get("profundidad_cm"),
                "cantidad_lecturas": candidate.get("count", 0),
                "ultima_lectura": candidate.get("last_dt") or candidate.get("last_ts"),
                "confianza": confidence,
                "provisional": provisional,
                "estado_asociacion": "provisional" if provisional else "asociada",
                "motivo": reason,
            })
    return proposals


def applicable_proposals(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if item["confianza"] in {"alta", "media"}]
