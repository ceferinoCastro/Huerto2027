from datetime import date, datetime, timedelta, timezone
from time import monotonic
from typing import Any
from uuid import uuid4

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, UpdateOne

from app.core.config import Settings
from app.services.compatibility import campaign_to_public, locality_from_college
from app.services.domain import DomainConflictError, DomainNotFoundError


LOCALITY_DEVICE_SN = {
    "pica": "z6-29235",
    "colchane": "z6-28148",
    "camina": "z6-28149",
    "huara": "z6-28150",
    "la-tirana": "z6-28108",
    "huayquique": None,
}

READINGS_SUMMARY_INDEX = "device_sn_variable_timestamp_utc_desc"
PLANT_MEASUREMENTS_COLLECTION = "mediciones_plantas"
PLANT_LOCALITY_DATE_INDEX = "localidad_fecha_asc"
PLANT_UNIQUE_MEASUREMENT_INDEX = "localidad_ciclo_fecha_planta_unique"
HANNA_MEASUREMENTS_COLLECTION = "mediciones_hanna"
HANNA_LOCALITY_DATE_INDEX = "hanna_localidad_fecha_asc"
HANNA_UNIQUE_MEASUREMENT_INDEX = "hanna_localidad_serial_datetime_unique"
HANNA_LOCALITY_VALID_INDEX = "hanna_localidad_valido_asc"
HANNA_SERIAL_DATETIME_INDEX = "hanna_serial_datetime_unique"
HANNA_DATALOGGERS_COLLECTION = "dataloggers_hanna"
HANNA_SERIAL_INDEX = "hanna_serial_unique"
HANNA_COLLEGE_INDEX = "hanna_colegio_asc"
HANNA_COLLEGE_STATE_INDEX = "hanna_colegio_estado_asc"
HANNA_ACTIVE_COLLEGE_INDEX = "hanna_activo_por_colegio_unique"
CAMPAIGNS_COLLECTION = "campania"
CAMPAIGN_COLLEGE_INDEX = "campania_colegio_asc"
CAMPAIGN_COLLEGE_STATE_INDEX = "campania_colegio_estado_asc"
CAMPAIGN_DATES_INDEX = "campania_fechas_asc"
CAMPAIGN_ACTIVE_COLLEGE_INDEX = "campania_activa_por_colegio_unique"
SENSOR_ASSOCIATIONS_COLLECTION = "asociaciones_sensores"
SENSOR_ASSOCIATION_UNIQUE_INDEX = "asociacion_colegio_variable_unique"
SENSOR_ASSOCIATION_LOCALITY_INDEX = "asociacion_localidad_orden"
CARTELS_COLLECTION = "carteles_educativos"
CARTEL_ORDEN_INDEX = "cartel_orden_asc"
CARTELS_CACHE_TTL_SECONDS = 30


# Variables nativas del sensor ATMOS 14 que deben ofrecerse siempre en el
# selector de variable técnica, incluso sin lecturas previas en `lecturas`
# para esa clave exacta (p. ej. "Percent Relative Humidity" recién agregada).
ATMOS_14_SENSOR_NAME = "ATMOS 14"
ATMOS_14_BASE_VARIABLES: dict[str, str] = {
    "Air Temperature": "°C",
    "Vapor Pressure": "kPa",
    "VPD": "kPa",
    "Atmospheric Pressure": "kPa",
    "Percent Relative Humidity": "%",
}


def _with_atmos_14_fallback_variables(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Guarantee every base ATMOS 14 variable appears, even without readings."""
    atmos_documents = [
        document for document in documents
        if document.get("sensor_name") == ATMOS_14_SENSOR_NAME
    ]
    if not atmos_documents:
        return documents

    reference = atmos_documents[0]
    present_variables = {document.get("variable") for document in atmos_documents}
    missing_variables = [
        variable for variable in ATMOS_14_BASE_VARIABLES
        if variable not in present_variables
    ]
    if not missing_variables:
        return documents

    return documents + [
        {
            "device_sn": reference.get("device_sn"),
            "sensor_sn": reference.get("sensor_sn"),
            "sensor_name": ATMOS_14_SENSOR_NAME,
            "variable": variable,
            "value": None,
            "units": ATMOS_14_BASE_VARIABLES[variable],
            "datetime": None,
            "timestamp_utc": None,
        }
        for variable in missing_variables
    ]


def build_readings_summary_pipeline(device_sn: str) -> list[dict[str, Any]]:
    """Build the aggregation shared by the endpoint and its diagnostics."""
    return [
        {"$match": {"device_sn": device_sn}},
        {"$sort": {"variable": 1, "timestamp_utc": DESCENDING}},
        {
            "$group": {
                "_id": "$variable",
                "document": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$document"}},
        {"$limit": 100},
    ]


def summarize_explain(explain: dict[str, Any]) -> dict[str, Any]:
    """Extract safe execution metrics and scan stages from an explain result."""
    execution_stats = explain.get("executionStats", {})
    stages: set[str] = set()
    index_names: set[str] = set()
    nested_execution_stats: list[dict[str, Any]] = []

    def collect_stages(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("executionStats"), dict):
                nested_execution_stats.append(value["executionStats"])
            stage = value.get("stage")
            if stage in {"COLLSCAN", "IXSCAN", "DISTINCT_SCAN"}:
                stages.add(stage)
            index_name = value.get("indexName")
            if isinstance(index_name, str):
                index_names.add(index_name)
            for nested_value in value.values():
                collect_stages(nested_value)
        elif isinstance(value, list):
            for nested_value in value:
                collect_stages(nested_value)

    collect_stages(explain)
    if not execution_stats and nested_execution_stats:
        execution_stats = max(
            nested_execution_stats,
            key=lambda stats: stats.get("totalDocsExamined", 0),
        )
    return {
        "executionTimeMillis": execution_stats.get("executionTimeMillis"),
        "totalDocsExamined": execution_stats.get("totalDocsExamined"),
        "totalKeysExamined": execution_stats.get("totalKeysExamined"),
        "scanStages": sorted(stages),
        "usesCOLLSCAN": "COLLSCAN" in stages,
        "usesIXSCAN": bool({"IXSCAN", "DISTINCT_SCAN"} & stages),
        "indexNames": sorted(index_names),
    }


class MongoDatabase:
    """Own the asynchronous MongoDB client used by the API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncIOMotorClient | None = None
        self._database: AsyncIOMotorDatabase | None = None
        self._carteles_cache: list[dict[str, Any]] | None = None
        self._carteles_cache_at: float = 0.0

    async def connect(self) -> None:
        self._client = AsyncIOMotorClient(
            self._settings.mongodb_uri,
            serverSelectionTimeoutMS=self._settings.mongodb_timeout_ms,
        )
        self._database = self._client[self._settings.mongodb_database]

    async def ping(self) -> None:
        if self._client is None:
            raise RuntimeError("MongoDB client is not initialized")
        await self._client.admin.command("ping")

    async def list_collection_names(self) -> list[str]:
        """Return collection names using MongoDB's read-only list operation."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        return await self._database.list_collection_names()

    async def list_documents(
        self,
        collection_name: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read a bounded number of documents from a collection."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")

        safe_limit = max(1, min(limit, 100))
        cursor = self._database[collection_name].find({}).limit(safe_limit)
        return await cursor.to_list(length=safe_limit)

    async def sensor_association_inventory(self) -> dict[str, Any]:
        """Collect read-only evidence needed by the initial association dry-run."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        pipeline = [
            {"$match": {"value": {"$type": "number"}}},
            {"$group": {
                "_id": {
                    "device_sn": "$device_sn",
                    "sensor_sn": "$sensor_sn",
                    "sensor_name": "$sensor_name",
                    "variable": "$variable",
                    "units": "$units",
                },
                "count": {"$sum": 1},
                "last_ts": {"$max": "$timestamp_utc"},
                "last_dt": {"$max": "$datetime"},
            }},
        ]
        reading_groups = []
        async for item in self._database["lecturas"].aggregate(pipeline, allowDiskUse=True):
            reading_groups.append({**item.pop("_id"), **item})
        hanna_pipeline = [
            {"$match": {"valido": True}},
            {"$project": {
                "serial_hanna": {"$ifNull": ["$serial_hanna", "$equipo_serial"]},
                "datetime_local": 1,
            }},
            {"$group": {
                "_id": "$serial_hanna",
                "count": {"$sum": 1},
                "last": {"$max": "$datetime_local"},
            }},
        ]
        hanna_groups = []
        async for item in self._database[HANNA_MEASUREMENTS_COLLECTION].aggregate(hanna_pipeline):
            hanna_groups.append({"serial_hanna": item["_id"], "count": item["count"], "last": item.get("last")})
        return {
            "colegios": await self._database["colegios"].find({}).to_list(length=100),
            "dataloggers": await self._database["dataloggers"].find({}).to_list(length=100),
            "sensores": await self._database["sensores"].find({}).to_list(length=1000),
            "variables": await self._database["variables"].find({}).to_list(length=1000),
            "lecturas": reading_groups,
            "dataloggers_hanna": await self._database[HANNA_DATALOGGERS_COLLECTION].find({}).to_list(length=1000),
            "hanna": hanna_groups,
            "asociaciones": await self._database[SENSOR_ASSOCIATIONS_COLLECTION].find({}).to_list(length=1000),
        }

    async def _ensure_index(
        self,
        collection: Any,
        keys: list[tuple[str, int]],
        *,
        name: str,
        unique: bool = False,
    ) -> None:
        """Create an index, replacing any stale definition under the same name.

        `create_index` raises IndexKeySpecsConflict (code 86) if an index with
        this `name` already exists with a different key spec — this happens
        silently whenever the collection's real indexes drift from what the
        code declares (e.g. a manually created or since-changed index). Since
        this runs on every association save, that conflict surfaces as an
        opaque 503 to the frontend instead of the actual schema issue.
        """
        existing = await collection.index_information()
        current = existing.get(name)
        if current is not None and (
            list(current.get("key", [])) != list(keys)
            or bool(current.get("unique", False)) != unique
        ):
            await collection.drop_index(name)
        await collection.create_index(keys, name=name, unique=unique)

    async def ensure_sensor_association_indexes(self) -> None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[SENSOR_ASSOCIATIONS_COLLECTION]
        await self._ensure_index(
            collection,
            [("colegio_id", ASCENDING), ("clave_educativa", ASCENDING)],
            name=SENSOR_ASSOCIATION_UNIQUE_INDEX,
            unique=True,
        )
        await self._ensure_index(
            collection,
            [("localidad", ASCENDING)],
            name=SENSOR_ASSOCIATION_LOCALITY_INDEX,
        )

    async def list_sensor_associations(self, locality: str) -> list[dict[str, Any]]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        return await self._database[SENSOR_ASSOCIATIONS_COLLECTION].find(
            {"localidad": locality}
        ).to_list(length=100)

    async def sensor_association(
        self, locality: str, educational_variable: str
    ) -> dict[str, Any] | None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        return await self._database[SENSOR_ASSOCIATIONS_COLLECTION].find_one({
            "localidad": locality,
            "clave_educativa": educational_variable,
            "estado_asociacion": {"$in": ["asociada", "provisional"]},
        })

    async def ensure_cartel_indexes(self) -> None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[CARTELS_COLLECTION]
        await collection.create_index([("orden", ASCENDING)], name=CARTEL_ORDEN_INDEX)
        # No hace falta índice único adicional: _id ya es clave_educativa,
        # Mongo garantiza su unicidad nativamente.

    def _invalidate_carteles_cache(self) -> None:
        self._carteles_cache = None

    async def list_carteles(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Catálogo completo de carteles, cacheado en proceso por TTL corto."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        now = monotonic()
        if (
            not force_refresh
            and self._carteles_cache is not None
            and now - self._carteles_cache_at < CARTELS_CACHE_TTL_SECONDS
        ):
            return self._carteles_cache
        items = await self._database[CARTELS_COLLECTION].find({}).sort(
            "orden", ASCENDING
        ).to_list(length=500)
        self._carteles_cache = items
        self._carteles_cache_at = now
        return items

    async def create_cartel(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_cartel_indexes()
        now = datetime.now(timezone.utc)
        document = {**data, "_id": data["clave_educativa"], "created_at": now, "updated_at": now}
        try:
            await self._database[CARTELS_COLLECTION].insert_one(document)
        finally:
            self._invalidate_carteles_cache()
        return document

    async def update_cartel(self, clave: str, data: dict[str, Any]) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        document = {**data, "updated_at": datetime.now(timezone.utc)}
        result = await self._database[CARTELS_COLLECTION].find_one_and_update(
            {"_id": clave},
            {"$set": document},
            return_document=True,
        )
        self._invalidate_carteles_cache()
        if result is None:
            raise DomainNotFoundError("Cartel no encontrado")
        return result

    async def delete_cartel(self, clave: str) -> None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        linked = await self._database[SENSOR_ASSOCIATIONS_COLLECTION].count_documents({
            "clave_educativa": clave,
            "estado_asociacion": {"$in": ["asociada", "provisional"]},
        })
        if linked:
            raise DomainConflictError("No se puede eliminar un cartel con asociaciones activas")
        result = await self._database[CARTELS_COLLECTION].delete_one({"_id": clave})
        self._invalidate_carteles_cache()
        if not result.deleted_count:
            raise DomainNotFoundError("Cartel no encontrado")

    async def _hanna_serials_for_college(self, college_id: str) -> list[str]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        documents = await self._database[HANNA_DATALOGGERS_COLLECTION].find(
            {"colegio_id": college_id}, {"_id": 0, "serial_hanna": 1}
        ).to_list(length=1000)
        return [item["serial_hanna"] for item in documents if item.get("serial_hanna")]

    async def latest_hanna_field_for_college(
        self,
        college_id: str,
        field: str,
    ) -> dict[str, Any]:
        """Resolve the newest valid Hanna field across all historical college equipment."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        if field not in {"ph_avg", "ec_avg_ms_cm", "temp_avg_c"}:
            raise ValueError("Campo Hanna no soportado")
        equipment = await self._database[HANNA_DATALOGGERS_COLLECTION].find(
            {"colegio_id": college_id},
            {
                "_id": 0,
                "serial_hanna": 1,
                "modelo": 1,
                "instrument_id": 1,
                "estado": 1,
            },
        ).to_list(length=1000)
        serials = [item["serial_hanna"] for item in equipment if item.get("serial_hanna")]
        if not serials:
            return {"estado": "sin_equipo_hanna", "documento": None}
        default_identity = next(
            (item for item in equipment if item.get("estado") == "activo"),
            equipment[0],
        )
        empty_identity = {
            "documento": None,
            "serial_hanna": default_identity.get("serial_hanna"),
            "modelo": default_identity.get("modelo"),
            "instrument_id": default_identity.get("instrument_id"),
            "estado_equipo": default_identity.get("estado"),
        }
        serial_filter = {
            "$or": [
                {"serial_hanna": {"$in": serials}},
                {"equipo_serial": {"$in": serials}},
            ]
        }
        collection = self._database[HANNA_MEASUREMENTS_COLLECTION]
        has_measurements = await collection.find_one(serial_filter, {"_id": 1})
        if has_measurements is None:
            return {"estado": "sin_datos", **empty_identity}
        document = await collection.find_one(
            {
                **serial_filter,
                "valido": True,
                field: {"$type": "number"},
            },
            {
                "_id": 0,
                field: 1,
                "fecha": 1,
                "hora": 1,
                "datetime_local": 1,
                "serial_hanna": 1,
                "equipo_serial": 1,
            },
            sort=[("datetime_local", DESCENDING)],
        )
        if document is None:
            return {"estado": "sin_datos_validos", **empty_identity}
        serial = document.get("serial_hanna") or document.get("equipo_serial")
        equipment_by_serial = {item["serial_hanna"]: item for item in equipment}
        identity = equipment_by_serial.get(serial, {})
        return {
            "estado": "ok",
            "documento": document,
            "serial_hanna": serial,
            "modelo": identity.get("modelo"),
            "instrument_id": identity.get("instrument_id"),
            "estado_equipo": identity.get("estado"),
        }

    async def latest_associated_measurement(
        self, association: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Resolve one educational association without consulting campaigns."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        source = association["source"]
        technical = association["variable_tecnica"]
        if source == "zentra":
            document = await self._database["lecturas"].find_one(
                {
                    "device_sn": association["device_sn"],
                    "sensor_sn": association["sensor_sn"],
                    "variable": technical,
                    "value": {"$type": "number"},
                },
                {"_id": 0, "value": 1, "units": 1, "datetime": 1, "timestamp_utc": 1},
                sort=[("timestamp_utc", DESCENDING)],
            )
            return document
        if source == "hanna":
            if technical not in {"ph_avg", "ec_avg_ms_cm", "temp_avg_c"}:
                return None
            resolved = await self.latest_hanna_field_for_college(
                association["colegio_id"], technical
            )
            document = resolved.get("documento")
            if resolved["estado"] != "ok" or document is None:
                return None
            return {
                "value": document[technical],
                "units": association.get("unidad"),
                "datetime": document.get("datetime_local"),
                "timestamp_utc": self._timestamp_from_value(document.get("datetime_local")),
                "serial_hanna": resolved.get("serial_hanna"),
                "modelo": resolved.get("modelo"),
                "instrument_id": resolved.get("instrument_id"),
            }
        if source == "manual":
            if technical not in {"altura_cm", "largo_raiz_cm"}:
                return None
            collection = self._database[PLANT_MEASUREMENTS_COLLECTION]
            latest = await collection.find_one(
                {"localidad": association["localidad"], technical: {"$type": "number"}},
                {"_id": 0, "fecha": 1},
                sort=[("fecha", DESCENDING)],
            )
            if latest is None:
                return None
            pipeline = [
                {"$match": {
                    "localidad": association["localidad"],
                    "fecha": latest["fecha"],
                    technical: {"$type": "number"},
                }},
                {"$group": {"_id": "$fecha", "value": {"$avg": f"${technical}"}}},
            ]
            rows = await collection.aggregate(pipeline).to_list(length=1)
            if not rows:
                return None
            return {
                "value": rows[0]["value"],
                "units": association.get("unidad"),
                "datetime": latest["fecha"],
                "timestamp_utc": self._timestamp_from_value(latest["fecha"]),
            }
        return None

    @staticmethod
    def _timestamp_from_value(value: Any) -> int | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())

    async def associated_measurement_series(
        self,
        association: dict[str, Any],
        since_timestamp: int,
        until_timestamp: int,
    ) -> list[dict[str, Any]]:
        """Read a series from the source selected by the association."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        source = association["source"]
        technical = association["variable_tecnica"]
        if source == "zentra":
            cursor = self._database["lecturas"].find(
                {
                    "device_sn": association["device_sn"],
                    "sensor_sn": association["sensor_sn"],
                    "variable": technical,
                    "value": {"$type": "number"},
                    "timestamp_utc": {"$gte": since_timestamp, "$lte": until_timestamp},
                },
                {"_id": 0, "value": 1, "datetime": 1, "timestamp_utc": 1},
            ).sort("timestamp_utc", ASCENDING)
            return await cursor.to_list(length=200000)
        start_iso = datetime.fromtimestamp(since_timestamp, timezone.utc).replace(tzinfo=None).isoformat()
        end_iso = datetime.fromtimestamp(until_timestamp, timezone.utc).replace(tzinfo=None).isoformat()
        if source == "hanna":
            if technical not in {"ph_avg", "ec_avg_ms_cm", "temp_avg_c"}:
                return []
            serials = await self._hanna_serials_for_college(association["colegio_id"])
            if not serials:
                return []
            cursor = self._database[HANNA_MEASUREMENTS_COLLECTION].find(
                {
                    "$or": [
                        {"serial_hanna": {"$in": serials}},
                        {"equipo_serial": {"$in": serials}},
                    ],
                    "valido": True,
                    technical: {"$type": "number"},
                    "datetime_local": {"$gte": start_iso, "$lte": end_iso},
                },
                {"_id": 0, technical: 1, "datetime_local": 1},
            ).sort("datetime_local", ASCENDING)
            documents = await cursor.to_list(length=200000)
            return [
                {
                    "value": item[technical],
                    "datetime": item.get("datetime_local"),
                    "timestamp_utc": self._timestamp_from_value(item.get("datetime_local")),
                }
                for item in documents
            ]
        if source == "manual":
            if technical not in {"altura_cm", "largo_raiz_cm"}:
                return []
            start_date, end_date = start_iso[:10], end_iso[:10]
            pipeline = [
                {"$match": {
                    "localidad": association["localidad"],
                    "fecha": {"$gte": start_date, "$lte": end_date},
                    technical: {"$type": "number"},
                }},
                {"$group": {
                    "_id": "$fecha",
                    "value": {"$avg": f"${technical}"},
                    "plantas_medidas": {"$sum": 1},
                }},
                {"$sort": {"_id": ASCENDING}},
            ]
            documents = await self._database[PLANT_MEASUREMENTS_COLLECTION].aggregate(pipeline).to_list(length=5000)
            return [
                {
                    "value": item["value"],
                    "datetime": item["_id"],
                    "timestamp_utc": self._timestamp_from_value(item["_id"]),
                    "plantas_medidas": item["plantas_medidas"],
                }
                for item in documents
            ]
        return []

    async def campaign_period(self, campaign_id: str, college_id: str) -> dict[str, str]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        campaigns = await self.campaigns_for_college(college_id)
        campaign = next((item for item in campaigns if item["_id"] == campaign_id), None)
        if campaign is None or not campaign.get("fecha_siembra"):
            raise DomainNotFoundError("Campaña no encontrada para este colegio")
        end = campaign.get("fecha_cosecha_real") or campaign.get("fecha_cosecha_estimada")
        if not end:
            end = datetime.now(timezone.utc).date().isoformat()
        return {"desde": campaign["fecha_siembra"], "hasta": end}

    async def _validate_sensor_association(self, data: dict[str, Any]) -> None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        carteles = {item["_id"] for item in await self.list_carteles()}
        if data["clave_educativa"] not in carteles:
            raise DomainNotFoundError("La clave educativa no corresponde a ningún cartel existente")
        college = await self.college_by_id(data["colegio_id"])
        if locality_from_college(college) != data["localidad"]:
            raise DomainConflictError("El colegio no corresponde a la localidad indicada")
        if data["source"] == "zentra":
            # Import diferido: evita el ciclo sensor_associations -> mongodb (LOCALITY_DEVICE_SN).
            from app.services.sensor_associations import _VARIABLE_ALIASES

            variable = data["variable_tecnica"]
            accepted_variables = [variable, *_VARIABLE_ALIASES.get(variable, ())]
            evidence = await self._database["lecturas"].find_one({
                "device_sn": data["device_sn"],
                "sensor_sn": data["sensor_sn"],
                "variable": {"$in": accepted_variables},
                "value": {"$type": "number"},
            })
            if evidence is None and variable in ATMOS_14_BASE_VARIABLES:
                # Variable técnica nativa del ATMOS 14 sin lecturas históricas todavía
                # (p. ej. recién habilitada). Se tolera si el sensor_sn corresponde a
                # un ATMOS 14 real con evidencia de otras lecturas en este dispositivo.
                evidence = await self._database["lecturas"].find_one({
                    "device_sn": data["device_sn"],
                    "sensor_sn": data["sensor_sn"],
                    "sensor_name": ATMOS_14_SENSOR_NAME,
                })
            if evidence is None:
                raise DomainConflictError(
                    "El sensor no tiene lecturas reales para esa variable técnica "
                    f"({variable!r}); verifica el sensor_sn o que el dispositivo haya "
                    "reportado datos para ese sensor."
                )
        elif data["source"] == "hanna":
            assignment = await self._database[HANNA_DATALOGGERS_COLLECTION].find_one({
                "serial_hanna": data["sensor_sn"],
                "colegio_id": data["colegio_id"],
            })
            if assignment is None:
                raise DomainConflictError("El serial Hanna no está asociado a este colegio")

    async def create_sensor_association(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_sensor_association_indexes()
        await self._validate_sensor_association(data)
        now = datetime.now(timezone.utc)
        document = {
            **data,
            "estado_asociacion": "asociada",
            "provisional": False,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._database[SENSOR_ASSOCIATIONS_COLLECTION].insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def update_sensor_association(self, association_id: str, data: dict[str, Any]) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        if not ObjectId.is_valid(association_id):
            raise DomainNotFoundError("Asociación no encontrada")
        await self._validate_sensor_association(data)
        document = {**data, "updated_at": datetime.now(timezone.utc)}
        result = await self._database[SENSOR_ASSOCIATIONS_COLLECTION].find_one_and_update(
            {"_id": ObjectId(association_id)},
            {"$set": document},
            return_document=True,
        )
        if result is None:
            raise DomainNotFoundError("Asociación no encontrada")
        return result

    async def delete_sensor_association(self, association_id: str) -> None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        if not ObjectId.is_valid(association_id):
            raise DomainNotFoundError("Asociación no encontrada")
        result = await self._database[SENSOR_ASSOCIATIONS_COLLECTION].delete_one({"_id": ObjectId(association_id)})
        if not result.deleted_count:
            raise DomainNotFoundError("Asociación no encontrada")

    async def upsert_initial_sensor_associations(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        """Apply the reviewed proposal without overwriting manually curated rows."""
        # Import diferido: evita el ciclo sensor_associations -> mongodb (LOCALITY_DEVICE_SN).
        from app.services.sensor_associations import _ASSOCIATION_FIELDS

        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_sensor_association_indexes()
        collection = self._database[SENSOR_ASSOCIATIONS_COLLECTION]
        created = updated = preserved = 0
        conflicts: list[dict[str, str]] = []
        for raw in documents:
            selector = {"colegio_id": raw["colegio_id"], "clave_educativa": raw["clave_educativa"]}
            current = await collection.find_one(selector)
            if current and current.get("origen_asignacion") != "inicial_automatica":
                preserved += 1
                if any(current.get(field) != raw.get(field) for field in ("source", "device_sn", "sensor_sn", "variable_tecnica")):
                    conflicts.append({"colegio_id": raw["colegio_id"], "clave_educativa": raw["clave_educativa"]})
                continue
            document = {key: value for key, value in raw.items() if key in _ASSOCIATION_FIELDS}
            result = await collection.update_one(
                selector,
                {"$set": document, "$setOnInsert": {"created_at": raw["updated_at"]}},
                upsert=True,
            )
            if result.upserted_id is not None:
                created += 1
            elif result.modified_count:
                updated += 1
            else:
                preserved += 1
        return {"created": created, "updated": updated, "preserved": preserved, "conflicts": conflicts}

    async def college_by_id(self, college_id: str) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        candidates: list[Any] = [college_id]
        if ObjectId.is_valid(college_id):
            candidates.append(ObjectId(college_id))
        document = await self._database["colegios"].find_one(
            {"$or": [
                {"_id": {"$in": candidates}},
                {"colegio_id": college_id},
                {"id": college_id},
            ]}
        )
        if document is None:
            raise DomainNotFoundError("Colegio no encontrado")
        return document

    async def college_by_locality(self, locality: str) -> dict[str, Any] | None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        documents = await self._database["colegios"].find({}).to_list(length=100)
        return next(
            (item for item in documents if locality_from_college(item) == locality),
            None,
        )

    async def latest_reading(self) -> dict[str, Any] | None:
        """Read the newest measurement using the supported date fields."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")

        readings = self._database["lecturas"]
        document = await readings.find_one(
            {"timestamp_utc": {"$exists": True}},
            sort=[("timestamp_utc", DESCENDING)],
        )
        if document is not None:
            return document

        return await readings.find_one(
            {"datetime": {"$exists": True}},
            sort=[("datetime", DESCENDING)],
        )

    async def latest_reading_by_locality(
        self,
        locality: str,
    ) -> dict[str, Any] | None:
        """Read the newest measurement matching a supported locality."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")

        if locality not in LOCALITY_DEVICE_SN:
            raise ValueError("Unsupported locality")
        device_sn = LOCALITY_DEVICE_SN[locality]
        if device_sn is None:
            return None

        readings = self._database["lecturas"]
        return await readings.find_one(
            {"device_sn": device_sn},
            sort=[("timestamp_utc", DESCENDING)],
        )

    async def latest_readings_summary_by_locality(
        self,
        locality: str,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Read the newest document for every variable of a locality."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        if locality not in LOCALITY_DEVICE_SN:
            raise ValueError("Unsupported locality")

        device_sn = LOCALITY_DEVICE_SN[locality]
        if device_sn is None:
            return None, []

        pipeline = build_readings_summary_pipeline(device_sn)
        cursor = self._database["lecturas"].aggregate(
            pipeline,
            hint=READINGS_SUMMARY_INDEX,
        )
        documents = await cursor.to_list(length=100)
        return device_sn, _with_atmos_14_fallback_variables(documents)

    async def readings_history_by_locality(
        self,
        locality: str,
        variable: str,
        since_timestamp: int,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Read non-null values in a time range for a locality and variable."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        if locality not in LOCALITY_DEVICE_SN:
            raise ValueError("Unsupported locality")

        device_sn = LOCALITY_DEVICE_SN[locality]
        if device_sn is None:
            return None, []

        cursor = (
            self._database["lecturas"]
            .find(
                {
                    "device_sn": device_sn,
                    "variable": variable,
                    "timestamp_utc": {"$gte": since_timestamp},
                    "value": {"$ne": None},
                },
                {
                    "_id": 0,
                    "datetime": 1,
                    "timestamp_utc": 1,
                    "value": 1,
                    "units": 1,
                },
            )
            .sort("timestamp_utc", ASCENDING)
            .hint(READINGS_SUMMARY_INDEX)
        )
        documents = [document async for document in cursor]
        return device_sn, documents

    async def ensure_plant_measurement_indexes(self) -> None:
        """Create only the indexes owned by `mediciones_plantas`."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[PLANT_MEASUREMENTS_COLLECTION]
        await collection.create_index(
            [("localidad", ASCENDING), ("fecha", ASCENDING)],
            name=PLANT_LOCALITY_DATE_INDEX,
        )
        await collection.create_index(
            [
                ("localidad", ASCENDING),
                ("ciclo_id", ASCENDING),
                ("fecha", ASCENDING),
                ("planta_numero", ASCENDING),
            ],
            name=PLANT_UNIQUE_MEASUREMENT_INDEX,
            unique=True,
        )

    async def upsert_plant_measurements(
        self,
        documents: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Insert or update daily plant heights without touching `lecturas`."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_plant_measurement_indexes()
        collection = self._database[PLANT_MEASUREMENTS_COLLECTION]
        created = 0
        updated = 0
        for document in documents:
            selector = {
                "localidad": document["localidad"],
                "ciclo_id": document["ciclo_id"],
                "fecha": document["fecha"],
                "planta_numero": document["planta_numero"],
            }
            result = await collection.update_one(
                selector,
                {
                    "$set": document,
                    "$setOnInsert": {"created_at": document["updated_at"]},
                },
                upsert=True,
            )
            if result.upserted_id is None:
                updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated}

    async def plant_measurement_averages(
        self,
        locality: str,
        since_date: str,
    ) -> list[dict[str, Any]]:
        """Return daily height and root-length averages for one locality.

        A day may have plant heights, a root-length measurement, or both —
        `$avg` ignores missing/non-numeric fields on its own, so each average
        is computed independently and comes back as `None` when that day has
        no documents carrying that particular field (old records included).
        """
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[PLANT_MEASUREMENTS_COLLECTION]
        has_height = {"$and": [{"$isNumber": "$altura_cm"}, {"$gt": ["$altura_cm", 0]}]}
        pipeline = [
            {
                "$match": {
                    "localidad": locality,
                    "fecha": {"$gte": since_date},
                    "$or": [
                        {"altura_cm": {"$type": "number", "$gt": 0}},
                        {"largo_raiz_cm": {"$type": "number", "$gt": 0}},
                    ],
                }
            },
            {
                "$group": {
                    "_id": "$fecha",
                    "altura_promedio_cm": {"$avg": "$altura_cm"},
                    "largo_raiz_promedio_cm": {"$avg": "$largo_raiz_cm"},
                    "plantas_medidas": {"$sum": {"$cond": [has_height, 1, 0]}},
                }
            },
            {"$sort": {"_id": ASCENDING}},
            {
                "$project": {
                    "_id": 0,
                    "fecha": "$_id",
                    "altura_promedio_cm": 1,
                    "largo_raiz_promedio_cm": 1,
                    "plantas_medidas": 1,
                }
            },
        ]
        cursor = collection.aggregate(pipeline)
        return await cursor.to_list(length=365)

    async def plant_measurements_by_date(
        self,
        locality: str,
        measurement_date: str,
        cycle_id: str,
    ) -> list[dict[str, Any]]:
        """Return individual measurements used to refill the daily form."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[PLANT_MEASUREMENTS_COLLECTION]
        cursor = collection.find(
            {
                "localidad": locality,
                "ciclo_id": cycle_id,
                "fecha": measurement_date,
            },
            {
                "_id": 0,
                "planta_numero": 1,
                "altura_cm": 1,
                "largo_raiz_cm": 1,
                "observacion": 1,
            },
        ).sort("planta_numero", ASCENDING)
        return await cursor.to_list(length=1000)

    async def delete_plant_root_length_placeholder(
        self,
        locality: str,
        cycle_id: str,
        measurement_date: str,
    ) -> None:
        """Remove the sentinel planta_numero=0 document once a real plant height exists for that day."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[PLANT_MEASUREMENTS_COLLECTION]
        await collection.delete_one({
            "localidad": locality,
            "ciclo_id": cycle_id,
            "fecha": measurement_date,
            "planta_numero": 0,
        })

    async def ensure_hanna_measurement_indexes(self) -> None:
        """Create indexes owned exclusively by `mediciones_hanna`."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[HANNA_MEASUREMENTS_COLLECTION]
        await collection.create_index(
            [("localidad", ASCENDING), ("fecha", ASCENDING)],
            name=HANNA_LOCALITY_DATE_INDEX,
        )
        await collection.create_index(
            [
                ("localidad", ASCENDING),
                ("equipo_serial", ASCENDING),
                ("datetime_local", ASCENDING),
            ],
            name=HANNA_UNIQUE_MEASUREMENT_INDEX,
            unique=True,
        )
        await collection.create_index(
            [("localidad", ASCENDING), ("valido", ASCENDING)],
            name=HANNA_LOCALITY_VALID_INDEX,
        )
        await collection.create_index(
            [("serial_hanna", ASCENDING), ("datetime_local", ASCENDING)],
            name=HANNA_SERIAL_DATETIME_INDEX,
            unique=True,
            partialFilterExpression={"serial_hanna": {"$type": "string"}},
        )

    async def upsert_hanna_measurements(
        self,
        documents: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Insert or update Hanna rows without touching Zentra readings."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_hanna_measurement_indexes()
        operations = []
        for document in documents:
            serial = document.get("serial_hanna") or document["equipo_serial"]
            selector = {
                "datetime_local": document["datetime_local"],
                "$or": [
                    {"serial_hanna": serial},
                    {"equipo_serial": serial},
                ],
            }
            operations.append(
                UpdateOne(
                    selector,
                    {
                        "$set": document,
                        "$setOnInsert": {"created_at": document["updated_at"]},
                    },
                    upsert=True,
                )
            )
        result = await self._database[HANNA_MEASUREMENTS_COLLECTION].bulk_write(
            operations,
            ordered=False,
        )
        return {
            "created": result.upserted_count,
            "updated": result.matched_count,
        }

    @staticmethod
    def _hanna_scope_filter(
        locality: str,
        assigned_serials: list[str] | None,
        registered_serials: list[str] | None,
    ) -> dict[str, Any]:
        if assigned_serials is None or registered_serials is None:
            return {"localidad": locality}
        legacy_filter: dict[str, Any] = {"localidad": locality}
        if registered_serials:
            legacy_filter["equipo_serial"] = {"$nin": registered_serials}
            legacy_filter["serial_hanna"] = {"$nin": registered_serials}
        if not assigned_serials:
            return legacy_filter
        return {
            "$or": [
                {"serial_hanna": {"$in": assigned_serials}},
                {"equipo_serial": {"$in": assigned_serials}},
                legacy_filter,
            ]
        }

    async def hanna_scope_for_locality(
        self,
        locality: str,
    ) -> tuple[list[str], list[str]]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        college = await self.college_by_locality(locality)
        assignments = await self._database[HANNA_DATALOGGERS_COLLECTION].find(
            {}, {"_id": 0, "serial_hanna": 1, "colegio_id": 1}
        ).to_list(length=1000)
        registered = [item["serial_hanna"] for item in assignments]
        if college is None:
            return [], registered
        college_id = str(college.get("colegio_id") or college.get("id") or college["_id"])
        assigned = [
            item["serial_hanna"]
            for item in assignments
            if str(item.get("colegio_id")) == college_id
        ]
        return assigned, registered

    async def hanna_measurements_summary(
        self,
        locality: str,
        assigned_serials: list[str] | None = None,
        registered_serials: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Summarize all Hanna imports for one locality."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        pipeline = [
            {"$match": self._hanna_scope_filter(locality, assigned_serials, registered_serials)},
            {"$sort": {"updated_at": DESCENDING}},
            {
                "$group": {
                    "_id": None,
                    "ultima_carga": {"$first": "$updated_at"},
                    "equipo_serial": {"$first": "$equipo_serial"},
                    "archivos": {"$addToSet": "$archivo_nombre"},
                    "total_registros": {"$sum": 1},
                    "total_validos": {
                        "$sum": {"$cond": ["$valido", 1, 0]}
                    },
                    "fecha_minima": {"$min": "$fecha"},
                    "fecha_maxima": {"$max": "$fecha"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "ultima_carga": 1,
                    "equipo_serial": 1,
                    "archivos_cargados": {"$size": "$archivos"},
                    "total_registros": 1,
                    "total_validos": 1,
                    "total_invalidos": {
                        "$subtract": ["$total_registros", "$total_validos"]
                    },
                    "fecha_minima": 1,
                    "fecha_maxima": 1,
                }
            },
        ]
        cursor = self._database[HANNA_MEASUREMENTS_COLLECTION].aggregate(
            pipeline
        )
        documents = await cursor.to_list(length=1)
        return documents[0] if documents else None

    async def hanna_daily_temperature_series(
        self,
        locality: str,
        days: int,
        assigned_serials: list[str] | None = None,
        registered_serials: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the latest daily water-temperature averages from Hanna data."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[HANNA_MEASUREMENTS_COLLECTION]
        valid_filter = {
            **self._hanna_scope_filter(locality, assigned_serials, registered_serials),
            "valido": True,
            "temp_avg_c": {"$type": "number", "$gt": 0, "$lt": 50},
        }
        latest = await collection.find_one(
            valid_filter,
            {"_id": 0, "fecha": 1},
            sort=[("fecha", DESCENDING)],
        )
        if not latest or not latest.get("fecha"):
            return []
        try:
            latest_date = date.fromisoformat(latest["fecha"])
        except (TypeError, ValueError):
            return []
        since_date = (latest_date - timedelta(days=days - 1)).isoformat()
        pipeline = [
            {
                "$match": {
                    **valid_filter,
                    "fecha": {"$gte": since_date, "$lte": latest_date.isoformat()},
                }
            },
            {
                "$group": {
                    "_id": "$fecha",
                    "valor": {"$avg": "$temp_avg_c"},
                }
            },
            {"$sort": {"_id": ASCENDING}},
            {"$project": {"_id": 0, "fecha": "$_id", "valor": 1}},
        ]
        cursor = collection.aggregate(pipeline)
        return await cursor.to_list(length=days)

    async def latest_hanna_temperature(
        self,
        locality: str,
        assigned_serials: list[str] | None = None,
        registered_serials: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return the latest valid Hanna water temperature for a locality."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        return await self._database[HANNA_MEASUREMENTS_COLLECTION].find_one(
            {
                **self._hanna_scope_filter(locality, assigned_serials, registered_serials),
                "valido": True,
                "temp_avg_c": {"$type": "number", "$gt": 0, "$lt": 50},
            },
            {
                "_id": 0,
                "temp_avg_c": 1,
                "fecha": 1,
                "hora": 1,
                "datetime_local": 1,
            },
            sort=[("datetime_local", DESCENDING)],
        )

    async def ensure_hanna_datalogger_indexes(self) -> None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[HANNA_DATALOGGERS_COLLECTION]
        await collection.create_index([("serial_hanna", ASCENDING)], name=HANNA_SERIAL_INDEX, unique=True)
        await collection.create_index([("colegio_id", ASCENDING)], name=HANNA_COLLEGE_INDEX)
        await collection.create_index([("colegio_id", ASCENDING), ("estado", ASCENDING)], name=HANNA_COLLEGE_STATE_INDEX)
        await collection.create_index(
            [("colegio_id", ASCENDING)],
            name=HANNA_ACTIVE_COLLEGE_INDEX,
            unique=True,
            partialFilterExpression={"estado": "activo"},
        )

    async def list_hanna_dataloggers(self) -> list[dict[str, Any]]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        return await self._database[HANNA_DATALOGGERS_COLLECTION].find(
            {}, {"_id": 0}
        ).sort([("colegio_nombre", ASCENDING), ("fecha_asignacion", DESCENDING)]).to_list(length=1000)

    async def hanna_datalogger(self, serial: str) -> dict[str, Any] | None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        return await self._database[HANNA_DATALOGGERS_COLLECTION].find_one(
            {"serial_hanna": serial.upper()}, {"_id": 0}
        )

    async def associate_hanna_datalogger(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_hanna_datalogger_indexes()
        collection = self._database[HANNA_DATALOGGERS_COLLECTION]
        serial = data["serial_hanna"].upper()
        if await collection.find_one({"serial_hanna": serial}):
            raise DomainConflictError("El serial Hanna ya está registrado")
        college = await self.college_by_id(data["colegio_id"])
        college_id = str(college.get("colegio_id") or college.get("id") or college["_id"])
        if await collection.find_one({"colegio_id": college_id, "estado": "activo"}):
            raise DomainConflictError("El colegio ya tiene un equipo Hanna activo; use Reemplazar equipo")
        now = datetime.now(timezone.utc)
        document = {
            **data,
            "serial_hanna": serial,
            "colegio_id": college_id,
            "colegio_nombre": college.get("nombre", "Colegio sin nombre"),
            "localidad": locality_from_college(college),
            "estado": "activo",
            "fecha_asignacion": str(data["fecha_asignacion"]),
            "fecha_baja": None,
            "reemplazado_por": None,
            "auditoria_asignaciones": [],
            "created_at": now,
            "updated_at": now,
        }
        await collection.insert_one(document)
        return {key: value for key, value in document.items() if key != "_id"}

    async def correct_hanna_assignment(
        self, serial: str, college_id: str, user: str | None
    ) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_hanna_datalogger_indexes()
        collection = self._database[HANNA_DATALOGGERS_COLLECTION]
        current = await collection.find_one({"serial_hanna": serial.upper()})
        if current is None:
            raise DomainNotFoundError("Equipo Hanna no encontrado")
        college = await self.college_by_id(college_id)
        new_id = str(college.get("colegio_id") or college.get("id") or college["_id"])
        if new_id != current["colegio_id"] and current["estado"] == "activo":
            active = await collection.find_one({"colegio_id": new_id, "estado": "activo", "serial_hanna": {"$ne": serial.upper()}})
            if active:
                raise DomainConflictError("El colegio de destino ya tiene un Hanna activo")
        now = datetime.now(timezone.utc)
        audit = {"colegio_anterior": current["colegio_id"], "colegio_nuevo": new_id, "fecha": now, "usuario": user}
        await collection.update_one(
            {"serial_hanna": serial.upper()},
            {"$set": {"colegio_id": new_id, "colegio_nombre": college.get("nombre", "Colegio sin nombre"), "localidad": locality_from_college(college), "updated_at": now}, "$push": {"auditoria_asignaciones": audit}},
        )
        return await self.hanna_datalogger(serial)  # type: ignore[return-value]

    async def replace_hanna_datalogger(self, serial: str, data: dict[str, Any]) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_hanna_datalogger_indexes()
        collection = self._database[HANNA_DATALOGGERS_COLLECTION]
        old = await collection.find_one({"serial_hanna": serial.upper()})
        if old is None:
            raise DomainNotFoundError("Equipo Hanna no encontrado")
        if old.get("estado") != "activo":
            raise DomainConflictError("Solo un equipo activo puede ser reemplazado")
        new_serial = data["serial_hanna_nuevo"].upper()
        existing = await collection.find_one({"serial_hanna": new_serial})
        if existing and existing.get("colegio_id") != old["colegio_id"]:
            raise DomainConflictError("El serial nuevo ya pertenece a otro colegio")
        if existing and existing.get("estado") == "activo":
            raise DomainConflictError("El serial nuevo ya está activo")
        now = datetime.now(timezone.utc)
        assignment_date = str(data["fecha_asignacion"])
        await collection.update_one(
            {"serial_hanna": serial.upper()},
            {"$set": {"estado": "reemplazado", "fecha_baja": assignment_date, "reemplazado_por": new_serial, "updated_at": now}},
        )
        try:
            if existing:
                await collection.update_one(
                    {"serial_hanna": new_serial},
                    {"$set": {"modelo": data["modelo"], "instrument_id": data["instrument_id"], "colegio_id": old["colegio_id"], "colegio_nombre": old["colegio_nombre"], "localidad": old.get("localidad"), "estado": "activo", "fecha_asignacion": assignment_date, "fecha_baja": None, "reemplazado_por": None, "updated_at": now}},
                )
            else:
                await collection.insert_one({"serial_hanna": new_serial, "modelo": data["modelo"], "instrument_id": data["instrument_id"], "colegio_id": old["colegio_id"], "colegio_nombre": old["colegio_nombre"], "localidad": old.get("localidad"), "estado": "activo", "fecha_asignacion": assignment_date, "fecha_baja": None, "reemplazado_por": None, "auditoria_asignaciones": [], "created_at": now, "updated_at": now})
        except Exception:
            await collection.update_one(
                {"serial_hanna": serial.upper()},
                {"$set": {"estado": "activo", "fecha_baja": None, "reemplazado_por": None, "updated_at": now}},
            )
            raise
        return {"anterior": await self.hanna_datalogger(serial), "nuevo": await self.hanna_datalogger(new_serial)}

    async def ensure_campaign_indexes(self) -> None:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[CAMPAIGNS_COLLECTION]
        await collection.create_index([("colegio_id", ASCENDING)], name=CAMPAIGN_COLLEGE_INDEX)
        await collection.create_index([("colegio_id", ASCENDING), ("estado", ASCENDING)], name=CAMPAIGN_COLLEGE_STATE_INDEX)
        await collection.create_index([("fecha_siembra", ASCENDING), ("fecha_cosecha_estimada", ASCENDING)], name=CAMPAIGN_DATES_INDEX)
        await collection.create_index([("colegio_id", ASCENDING)], name=CAMPAIGN_ACTIVE_COLLEGE_INDEX, unique=True, partialFilterExpression={"estado": "activa", "colegio_id": {"$type": "string"}})

    async def campaigns_for_college(self, college_id: str) -> list[dict[str, Any]]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        college = await self.college_by_id(college_id)
        canonical_id = str(college.get("colegio_id") or college.get("id") or college["_id"])
        aliases = [value for value in {college.get("nombre"), college.get("comuna"), locality_from_college(college)} if value]
        documents = await self._database[CAMPAIGNS_COLLECTION].find({"$or": [{"colegio_id": canonical_id}, {"colegio": {"$in": aliases}}]}).to_list(length=1000)
        normalized = [campaign_to_public(item, canonical_id) for item in documents]
        return sorted(normalized, key=lambda item: item.get("fecha_siembra") or "", reverse=True)

    async def active_campaign(self, college_id: str) -> dict[str, Any] | None:
        campaigns = await self.campaigns_for_college(college_id)
        return next((item for item in campaigns if item["estado"] == "activa"), None)

    async def create_campaign(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        await self.ensure_campaign_indexes()
        college = await self.college_by_id(data["colegio_id"])
        canonical_id = str(college.get("colegio_id") or college.get("id") or college["_id"])
        if await self.active_campaign(canonical_id):
            raise DomainConflictError("El colegio ya tiene una campaña activa")
        now = datetime.now(timezone.utc)
        locality = locality_from_college(college) or college.get("comuna") or college.get("nombre")
        crop = data["cultivo"].strip()
        sowing = str(data["fecha_siembra"])
        estimated = str(data["fecha_cosecha_estimada"])
        document = {
            "_id": f"camp_{uuid4().hex}",
            "colegio_id": canonical_id,
            "colegio": college.get("nombre", "Colegio sin nombre"),
            "nombre": f"{crop.capitalize()} — {str(locality).title()} — {sowing[:4]}",
            "cultivo": crop,
            "especie": crop,
            "fecha_siembra": sowing,
            "desde": sowing,
            "fecha_cosecha_estimada": estimated,
            "hasta": estimated,
            "fecha_cosecha_real": None,
            "estado": "activa",
            "observaciones": data.get("observaciones", ""),
            "rangos_variables": data.get("rangos_variables") or {},
            "created_at": now,
            "updated_at": now,
        }
        await self._database[CAMPAIGNS_COLLECTION].insert_one(document)
        return campaign_to_public(document, canonical_id)

    async def _active_campaign_document(self, campaign_id: str) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        identifiers: list[Any] = [campaign_id]
        if ObjectId.is_valid(campaign_id):
            identifiers.append(ObjectId(campaign_id))
        document = await self._database[CAMPAIGNS_COLLECTION].find_one(
            {"_id": {"$in": identifiers}}
        )
        if document is None:
            raise DomainNotFoundError("Campaña no encontrada")
        if campaign_to_public(document)["estado"] != "activa":
            raise DomainConflictError("La campaña ya no está activa")
        return document

    async def _save_campaign_change(
        self, document: dict[str, Any], changes: dict[str, Any],
        revision: int, action: str,
    ) -> dict[str, Any]:
        """Update only campaign fields, with atomic revision and audit checks."""
        current = campaign_to_public(document)
        if revision != current["revision"]:
            raise DomainConflictError("La campaña cambió. Vuelva a cargarla antes de guardar")
        now = datetime.now(timezone.utc)
        audit = {
            "accion": action, "fecha": now,
            "revision": revision + 1,
            "cambios": {key: {"anterior": current.get(key, document.get(key)), "nuevo": value}
                        for key, value in changes.items()},
        }
        updates = {**changes, "updated_at": now, "revision": revision + 1,
                   "historial_cambios": [*(document.get("historial_cambios") or []), audit]}
        query = {"_id": document["_id"], "estado": document.get("estado")}
        if "revision" in document:
            query["revision"] = document["revision"]
        else:
            query["revision"] = {"$exists": False}
        result = await self._database[CAMPAIGNS_COLLECTION].update_one(
            query, {"$set": updates}
        )
        if result.matched_count != 1:
            raise DomainConflictError("La campaña cambió. Vuelva a cargarla antes de guardar")
        return campaign_to_public({**document, **updates})

    async def update_campaign(self, campaign_id: str, data: dict[str, Any]) -> dict[str, Any]:
        document = await self._active_campaign_document(campaign_id)
        allowed = {"nombre", "cultivo", "fecha_siembra", "fecha_cosecha_estimada", "observaciones", "rangos_variables"}
        if set(data) - allowed - {"revision"}:
            raise DomainConflictError("Solo puede editar los datos de la campaña activa")
        changes = {key: value.strip() if isinstance(value, str) else value
                   for key, value in data.items() if key in allowed}
        if not changes:
            raise DomainConflictError("Debe modificar al menos un campo de la campaña")
        # rangos_variables puede quedar como {} (sin umbrales configurados): no es un campo obligatorio.
        if any(key in changes and not changes[key] for key in allowed - {"observaciones", "rangos_variables"}):
            raise DomainConflictError("Los campos obligatorios no pueden quedar vacíos")
        current = campaign_to_public(document)
        sowing = changes.get("fecha_siembra", current["fecha_siembra"])
        estimated = changes.get("fecha_cosecha_estimada", current["fecha_cosecha_estimada"])
        if sowing and estimated and estimated[:10] < sowing[:10]:
            raise DomainConflictError("La cosecha estimada no puede ser anterior a la siembra")
        for key, alias in (("cultivo", "especie"), ("fecha_siembra", "desde"),
                           ("fecha_cosecha_estimada", "hasta")):
            if key in changes:
                changes[alias] = changes[key]
        return await self._save_campaign_change(document, changes, data.get("revision", 0), "edicion")

    async def finish_campaign(self, campaign_id: str, data: dict[str, Any]) -> dict[str, Any]:
        document = await self._active_campaign_document(campaign_id)
        normalized = campaign_to_public(document)
        harvest_date = data["fecha_cosecha_real"]
        if normalized["fecha_siembra"] and harvest_date < normalized["fecha_siembra"][:10]:
            raise DomainConflictError("La cosecha real no puede ser anterior a la siembra")
        changes = {
            "estado": "finalizada", "fecha_cosecha_real": harvest_date,
            "resultado_final": data["resultado_final"],
            "observaciones_finales": data.get("observaciones_finales", ""),
        }
        return await self._save_campaign_change(document, changes, data.get("revision", 0), "finalizacion")

    async def cancel_campaign(self, campaign_id: str) -> dict[str, Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")
        collection = self._database[CAMPAIGNS_COLLECTION]
        document = await collection.find_one({"_id": campaign_id})
        if document is None:
            raise DomainNotFoundError("Campaña no encontrada")
        normalized = campaign_to_public(document)
        if normalized["estado"] != "activa":
            raise DomainConflictError("La campaña ya no está activa")
        now = datetime.now(timezone.utc)
        await collection.update_one({"_id": campaign_id}, {"$set": {"estado": "cancelada", "updated_at": now}})
        normalized.update({"estado": "cancelada", "updated_at": now})
        return normalized

    async def readings_performance_diagnostics(self) -> dict[str, Any]:
        """Inspect indexes and explain two read-only queries on readings."""
        if self._database is None:
            raise RuntimeError("MongoDB database is not initialized")

        readings = self._database["lecturas"]
        raw_indexes = await readings.list_indexes().to_list(length=100)
        indexes = [
            {
                "name": index.get("name"),
                "key": dict(index.get("key", {})),
            }
            for index in raw_indexes
        ]

        general_command = {
            "find": "lecturas",
            "filter": {"timestamp_utc": {"$exists": True, "$ne": None}},
            "sort": {"timestamp_utc": DESCENDING},
            "limit": 1,
            "maxTimeMS": self._settings.mongodb_timeout_ms,
        }
        pica_command = {
            "find": "lecturas",
            "filter": {"device_sn": LOCALITY_DEVICE_SN["pica"]},
            "sort": {"timestamp_utc": DESCENDING},
            "limit": 1,
            "maxTimeMS": self._settings.mongodb_timeout_ms,
        }

        general_explain = await self._database.command(
            {
                "explain": general_command,
                "verbosity": "executionStats",
            }
        )
        pica_explain = await self._database.command(
            {
                "explain": pica_command,
                "verbosity": "executionStats",
            }
        )
        pica_summary_explain = await self._database.command(
            {
                "explain": {
                    "aggregate": "lecturas",
                    "pipeline": build_readings_summary_pipeline(
                        LOCALITY_DEVICE_SN["pica"]
                    ),
                    "cursor": {},
                    "hint": READINGS_SUMMARY_INDEX,
                    "maxTimeMS": self._settings.mongodb_timeout_ms,
                },
                "verbosity": "executionStats",
            }
        )

        return {
            "indexes": indexes,
            "queries": {
                "ultima_general": summarize_explain(general_explain),
                "ultima_localidad_pica": summarize_explain(pica_explain),
                "resumen_localidad_pica": summarize_explain(
                    pica_summary_explain
                ),
            },
        }

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._database = None
