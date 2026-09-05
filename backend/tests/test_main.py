import asyncio
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
import pytest

from app.core.config import Settings
from app.db.mongodb import (
    HANNA_LOCALITY_DATE_INDEX,
    HANNA_LOCALITY_VALID_INDEX,
    HANNA_UNIQUE_MEASUREMENT_INDEX,
    LOCALITY_DEVICE_SN,
    MongoDatabase,
    PLANT_LOCALITY_DATE_INDEX,
    PLANT_UNIQUE_MEASUREMENT_INDEX,
)
from app.main import create_app
from app.services.hanna_csv import HannaCSVError, parse_hanna_csv


class FakeMongoDatabase:
    def __init__(
        self,
        available: bool = True,
        collection_names: list[str] | None = None,
        documents: dict[str, list[dict]] | None = None,
        latest_reading: dict | None = None,
        locality_readings: dict[str, dict] | None = None,
        locality_summaries: dict[str, tuple[str | None, list[dict]]] | None = None,
        locality_histories: dict[
            tuple[str, str], tuple[str | None, list[dict]]
        ]
        | None = None,
        performance_diagnostics: dict | None = None,
        plant_upsert_result: dict[str, int] | None = None,
        plant_averages: list[dict] | None = None,
        plant_measurements: list[dict] | None = None,
        hanna_upsert_results: list[dict[str, int]] | None = None,
        hanna_summary: dict | None = None,
        hanna_temperature_series: list[dict] | None = None,
        latest_hanna_temperature: dict | None = None,
    ) -> None:
        self.available = available
        self.collection_names = collection_names or []
        self.documents = documents or {}
        self.latest_reading_document = latest_reading
        self.locality_readings = locality_readings or {}
        self.locality_calls: list[str] = []
        self.locality_summaries = locality_summaries or {}
        self.summary_calls: list[str] = []
        self.locality_histories = locality_histories or {}
        self.history_calls: list[tuple[str, str, int]] = []
        self.performance_diagnostics = performance_diagnostics or {
            "indexes": [],
            "queries": {},
        }
        self.list_calls: list[tuple[str, int]] = []
        self.plant_upsert_result = plant_upsert_result or {
            "created": 0,
            "updated": 0,
        }
        self.plant_averages = plant_averages or []
        self.plant_measurements = plant_measurements or []
        self.plant_upsert_calls: list[list[dict]] = []
        self.plant_average_calls: list[tuple[str, str]] = []
        self.plant_measurement_calls: list[tuple[str, str, str]] = []
        self.hanna_upsert_results = hanna_upsert_results or [
            {"created": 0, "updated": 0}
        ]
        self.hanna_summary = hanna_summary
        self.hanna_upsert_calls: list[list[dict]] = []
        self.hanna_summary_calls: list[str] = []
        self.hanna_temperature_series = hanna_temperature_series or []
        self.hanna_temperature_series_calls: list[tuple[str, int]] = []
        self.latest_hanna_temperature_document = latest_hanna_temperature
        self.latest_hanna_temperature_calls: list[str] = []
        self.latest_hanna_field_calls: list[tuple[str, str]] = []
        self.hanna_dataloggers: dict[str, dict] = {}
        self.connected = False
        self.closed = False

    async def connect(self) -> None:
        self.connected = True

    async def ping(self) -> None:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")

    async def list_collection_names(self) -> list[str]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        return self.collection_names

    async def list_documents(
        self,
        collection_name: str,
        limit: int = 100,
    ) -> list[dict]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.list_calls.append((collection_name, limit))
        return self.documents.get(collection_name, [])[:limit]

    async def latest_reading(self) -> dict | None:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        return self.latest_reading_document

    async def latest_reading_by_locality(self, locality: str) -> dict | None:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.locality_calls.append(locality)
        return self.locality_readings.get(locality)

    async def latest_readings_summary_by_locality(
        self,
        locality: str,
    ) -> tuple[str | None, list[dict]]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.summary_calls.append(locality)
        return self.locality_summaries.get(locality, (None, []))

    async def readings_history_by_locality(
        self,
        locality: str,
        variable: str,
        since_timestamp: int,
    ) -> tuple[str | None, list[dict]]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.history_calls.append((locality, variable, since_timestamp))
        return self.locality_histories.get((locality, variable), (None, []))

    async def readings_performance_diagnostics(self) -> dict:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        return self.performance_diagnostics

    async def upsert_plant_measurements(
        self,
        documents: list[dict],
    ) -> dict[str, int]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.plant_upsert_calls.append(documents)
        return self.plant_upsert_result

    async def plant_measurement_averages(
        self,
        locality: str,
        since_date: str,
    ) -> list[dict]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.plant_average_calls.append((locality, since_date))
        return self.plant_averages

    async def plant_measurements_by_date(
        self,
        locality: str,
        measurement_date: str,
        cycle_id: str,
    ) -> list[dict]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.plant_measurement_calls.append(
            (locality, measurement_date, cycle_id)
        )
        return self.plant_measurements

    async def upsert_hanna_measurements(
        self,
        documents: list[dict],
    ) -> dict[str, int]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.hanna_upsert_calls.append(documents)
        index = min(
            len(self.hanna_upsert_calls) - 1,
            len(self.hanna_upsert_results) - 1,
        )
        return self.hanna_upsert_results[index]

    async def hanna_datalogger(self, serial: str) -> dict | None:
        return self.hanna_dataloggers.get(serial)

    async def college_by_locality(self, locality: str) -> dict:
        return {"_id": f"school-{locality}", "nombre": locality.title(), "comuna": locality}

    async def associate_hanna_datalogger(self, data: dict) -> dict:
        locality = str(data["colegio_id"]).removeprefix("school-")
        document = {
            **data,
            "colegio_id": str(data["colegio_id"]),
            "colegio_nombre": locality.title(),
            "localidad": locality,
            "estado": "activo",
            "fecha_asignacion": str(data["fecha_asignacion"]),
            "fecha_baja": None,
            "reemplazado_por": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.hanna_dataloggers[data["serial_hanna"]] = document
        return document

    async def hanna_scope_for_locality(self, locality: str) -> tuple[list[str], list[str]]:
        registered = list(self.hanna_dataloggers)
        assigned = [serial for serial, item in self.hanna_dataloggers.items() if item["localidad"] == locality]
        return assigned, registered

    async def hanna_measurements_summary(self, locality: str, *scope) -> dict | None:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.hanna_summary_calls.append(locality)
        return self.hanna_summary

    async def hanna_daily_temperature_series(
        self,
        locality: str,
        days: int,
        *scope,
    ) -> list[dict]:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.hanna_temperature_series_calls.append((locality, days))
        return self.hanna_temperature_series

    async def latest_hanna_temperature(self, locality: str, *scope) -> dict | None:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.latest_hanna_temperature_calls.append(locality)
        return self.latest_hanna_temperature_document

    async def latest_hanna_field_for_college(self, college_id: str, field: str) -> dict:
        if not self.available:
            raise RuntimeError("MongoDB is unavailable")
        self.latest_hanna_field_calls.append((college_id, field))
        equipment = next(
            (item for item in self.hanna_dataloggers.values() if item["colegio_id"] == college_id),
            None,
        )
        if equipment is None:
            return {"estado": "sin_equipo_hanna", "documento": None}
        document = self.latest_hanna_temperature_document
        identity = {
            "serial_hanna": equipment["serial_hanna"],
            "modelo": equipment.get("modelo"),
            "instrument_id": equipment.get("instrument_id"),
        }
        if document is None:
            return {"estado": "sin_datos", "documento": None, **identity}
        if document.get(field) is None:
            return {"estado": "sin_datos_validos", "documento": None, **identity}
        return {"estado": "ok", "documento": document, **identity}

    def close(self) -> None:
        self.closed = True


def build_test_app(database: FakeMongoDatabase):
    settings = Settings(_env_file=None, enable_diagnostics=True)
    return create_app(settings=settings, mongodb=database)


def build_hanna_csv(serial: str, instrument_id: str = "0003") -> bytes:
    metadata = [
        "Model;HI981420",
        f"Serial #;{serial}",
        f"Instrument ID;{instrument_id}",
        *[f"Metadata {index};valor" for index in range(4, 22)],
    ]
    header = "Date;Time;Min;Unit;Max;Unit;Avg;Unit;Min;Unit;Max;Unit;Avg;Unit;Min;Unit;Max;Unit;Avg;Unit;"
    valid = "07/07/2026;14:33:42;6,4;pH;6,8;pH;6,6;pH;1,0;mS/cm;1,2;mS/cm;1,1;mS/cm;21,0;°C;23,0;°C;22,0;°C;"
    invalid = "08/07/2026;14:33:42;0,0;pH;0,0;pH;0,0!!;pH;10,0;mS/cm;10,0;mS/cm;10,0;mS/cm;60,0;�C;60,0;�C;60,0;�C;"
    return ("\n".join([*metadata, header, valid, invalid]) + "\n").encode(
        "utf-16"
    )


def test_root_endpoint() -> None:
    database = FakeMongoDatabase()

    with TestClient(build_test_app(database)) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "aplicacion": "Huerto Escolar 2027 API",
        "backend": "FastAPI",
        "estado": "funcionando",
    }
    assert database.connected is True
    assert database.closed is True


def test_health_endpoint_when_mongodb_is_available() -> None:
    with TestClient(build_test_app(FakeMongoDatabase())) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mongodb": "connected"}


def test_health_endpoint_when_mongodb_is_unavailable() -> None:
    database = FakeMongoDatabase(available=False)

    with TestClient(build_test_app(database)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "mongodb": "unavailable",
    }


def test_collections_diagnostic_lists_names_in_stable_order() -> None:
    database = FakeMongoDatabase(
        collection_names=["mediciones", "huertos", "dispositivos"]
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get("/api/v1/diagnostico/colecciones")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "collections": ["dispositivos", "huertos", "mediciones"],
    }


def test_collections_diagnostic_when_mongodb_is_unavailable() -> None:
    database = FakeMongoDatabase(available=False)

    with TestClient(build_test_app(database)) as client:
        response = client.get("/api/v1/diagnostico/colecciones")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "collections": []}


def test_collections_diagnostic_can_be_disabled() -> None:
    settings = Settings(_env_file=None, enable_diagnostics=False)

    with TestClient(
        create_app(settings=settings, mongodb=FakeMongoDatabase())
    ) as client:
        response = client.get("/api/v1/diagnostico/colecciones")

    assert response.status_code == 404


def test_readings_performance_diagnostic_returns_safe_summary() -> None:
    database = FakeMongoDatabase(
        performance_diagnostics={
            "indexes": [
                {"name": "timestamp_utc_-1", "key": {"timestamp_utc": -1}}
            ],
            "queries": {
                "ultima_general": {
                    "executionTimeMillis": 2,
                    "totalDocsExamined": 1,
                    "totalKeysExamined": 1,
                    "scanStages": ["IXSCAN"],
                    "usesCOLLSCAN": False,
                    "usesIXSCAN": True,
                },
                "ultima_localidad_pica": {
                    "executionTimeMillis": 14,
                    "totalDocsExamined": 200,
                    "totalKeysExamined": 0,
                    "scanStages": ["COLLSCAN"],
                    "usesCOLLSCAN": True,
                    "usesIXSCAN": False,
                },
            },
        }
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get("/api/v1/diagnostico/lecturas/rendimiento")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "collection": "lecturas",
        **database.performance_diagnostics,
    }


def test_read_only_collection_endpoints_use_expected_names_and_limit() -> None:
    object_id = ObjectId()
    variable_id = ObjectId()
    sensor_id = ObjectId()
    database = FakeMongoDatabase(
        documents={
            "colegios": [{"_id": object_id, "nombre": "Colegio Norte"}],
            "variables": [{"_id": variable_id, "nombre": "humedad"}],
            "sensores": [{"_id": sensor_id, "codigo": "S-01"}],
        }
    )

    with TestClient(build_test_app(database)) as client:
        colegios_response = client.get("/api/v1/colegios")
        variables_response = client.get("/api/v1/variables")
        sensores_response = client.get("/api/v1/sensores")

    assert colegios_response.status_code == 200
    assert colegios_response.json() == {
        "status": "ok",
        "count": 1,
        "items": [{"_id": str(object_id), "nombre": "Colegio Norte"}],
    }
    assert variables_response.status_code == 200
    assert variables_response.json() == {
        "status": "ok",
        "count": 1,
        "items": [{"_id": str(variable_id), "nombre": "humedad"}],
    }
    assert sensores_response.status_code == 200
    assert sensores_response.json() == {
        "status": "ok",
        "count": 1,
        "items": [{"_id": str(sensor_id), "codigo": "S-01"}],
    }
    assert database.list_calls == [
        ("colegios", 100),
        ("variables", 100),
        ("sensores", 100),
    ]


def test_latest_reading_returns_valid_json_with_mongodb_types() -> None:
    reading_id = ObjectId()
    sensor_id = ObjectId()
    database = FakeMongoDatabase(
        latest_reading={
            "_id": reading_id,
            "sensor": {"_id": sensor_id},
            "timestamp_utc": datetime(2026, 8, 30, 14, 5, tzinfo=timezone.utc),
            "fecha": date(2026, 8, 30),
            "nombre": "temperatura",
            "muestras": 12,
            "valor": 23.5,
            "valida": False,
            "observacion": None,
        }
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get("/api/v1/lecturas/ultima")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ok",
        "item": {
            "_id": str(reading_id),
            "sensor": {"_id": str(sensor_id)},
            "timestamp_utc": "2026-08-30T14:05:00+00:00",
            "fecha": "2026-08-30",
            "nombre": "temperatura",
            "muestras": 12,
            "valor": 23.5,
            "valida": False,
            "observacion": None,
        },
    }
    assert b'"valida":false' in response.content
    assert b'"observacion":null' in response.content


def test_collection_endpoint_returns_normalized_empty_list() -> None:
    with TestClient(build_test_app(FakeMongoDatabase())) as client:
        response = client.get("/api/v1/colegios")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "count": 0, "items": []}


def test_latest_reading_returns_null_item_when_collection_is_empty() -> None:
    with TestClient(build_test_app(FakeMongoDatabase())) as client:
        response = client.get("/api/v1/lecturas/ultima")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "item": None}
    assert b'"item":null' in response.content


def test_latest_reading_by_locality_normalizes_and_serializes_item() -> None:
    reading_id = ObjectId()
    database = FakeMongoDatabase(
        locality_readings={
            "camina": {
                "_id": reading_id,
                "timestamp_utc": datetime(
                    2026, 8, 30, 15, 30, tzinfo=timezone.utc
                ),
                "activa": False,
                "observacion": None,
            }
        }
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get("/api/v1/localidades/Cami%C3%B1a/lecturas/ultima")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "localidad": "camina",
        "item": {
            "_id": str(reading_id),
            "timestamp_utc": "2026-08-30T15:30:00+00:00",
            "activa": False,
            "observacion": None,
        },
    }
    assert database.locality_calls == ["camina"]


def test_latest_reading_by_locality_returns_null_when_not_found() -> None:
    database = FakeMongoDatabase()

    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/localidades/la-tirana/lecturas/ultima"
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "localidad": "la-tirana",
        "item": None,
    }


def test_latest_reading_by_locality_rejects_unknown_locality() -> None:
    with TestClient(build_test_app(FakeMongoDatabase())) as client:
        response = client.get("/api/v1/localidades/iquique/lecturas/ultima")

    assert response.status_code == 404
    assert response.json() == {"detail": "Localidad no soportada"}


def test_locality_device_map_matches_configured_devices() -> None:
    assert LOCALITY_DEVICE_SN == {
        "pica": "z6-29235",
        "colchane": "z6-28148",
        "camina": "z6-28149",
        "huara": "z6-28150",
        "la-tirana": "z6-28108",
        "huayquique": None,
    }


def test_locality_summary_orders_variables_and_serializes_items() -> None:
    water_id = ObjectId()
    battery_id = ObjectId()
    database = FakeMongoDatabase(
        locality_summaries={
            "pica": (
                "z6-29235",
                [
                    {
                        "_id": battery_id,
                        "variable": "Battery Percent",
                        "value": 87,
                    },
                    {
                        "_id": ObjectId(),
                        "variable": "Custom Variable",
                        "value": None,
                    },
                    {
                        "_id": water_id,
                        "variable": "Water Content",
                        "value": 31.5,
                        "units": "%",
                        "datetime": datetime(
                            2026, 8, 30, 16, tzinfo=timezone.utc
                        ),
                        "timestamp_utc": 1788105600,
                        "sensor_name": "TEROS 12",
                        "sensor_sn": "sensor-01",
                        "active": True,
                    },
                ],
            )
        }
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get("/api/v1/localidades/pica/lecturas/resumen")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["localidad"] == "pica"
    assert body["device_sn"] == "z6-29235"
    assert body["count"] == 3
    assert [item["variable"] for item in body["items"]] == [
        "Water Content",
        "Battery Percent",
        "Custom Variable",
    ]
    assert body["items"][0]["_id"] == str(water_id)
    assert body["items"][0]["value"] == 31.5
    assert body["items"][0]["units"] == "%"
    assert body["items"][0]["datetime"] == "2026-08-30T16:00:00+00:00"
    assert body["items"][0]["timestamp_utc"] == 1788105600
    assert body["items"][0]["sensor_name"] == "TEROS 12"
    assert body["items"][0]["sensor_sn"] == "sensor-01"
    assert body["items"][0]["active"] is True
    assert body["items"][1]["_id"] == str(battery_id)
    assert body["items"][1]["units"] is None
    assert body["items"][2]["value"] is None
    for item in body["items"]:
        assert {
            "variable",
            "value",
            "units",
            "datetime",
            "timestamp_utc",
            "sensor_name",
            "sensor_sn",
        }.issubset(item)
    assert b'"active":true' in response.content
    assert b'"value":null' in response.content
    assert database.summary_calls == ["pica"]


def test_locality_summary_without_device_returns_empty_items() -> None:
    database = FakeMongoDatabase(
        locality_summaries={"huayquique": (None, [])}
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/localidades/huayquique/lecturas/resumen"
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "localidad": "huayquique",
        "device_sn": None,
        "count": 0,
        "items": [],
    }


def test_locality_summary_with_device_and_no_readings_returns_empty_items() -> None:
    database = FakeMongoDatabase(
        locality_summaries={"pica": ("z6-29235", [])}
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get("/api/v1/localidades/pica/lecturas/resumen")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "localidad": "pica",
        "device_sn": "z6-29235",
        "count": 0,
        "items": [],
    }


def test_locality_history_returns_representative_smoothed_series() -> None:
    documents = [
        {
            "datetime": datetime.fromtimestamp(
                1_700_000_000 + index * 60,
                tz=timezone.utc,
            ),
            "timestamp_utc": 1_700_000_000 + index * 60,
            "value": 80.0 if index == 10 else float(index),
            "units": "%",
        }
        for index in range(20)
    ]
    documents.insert(
        10,
        {
            "datetime": "2023-11-14T22:22:00+00:00",
            "timestamp_utc": 1_700_000_500,
            "value": None,
            "units": "%",
        },
    )
    database = FakeMongoDatabase(
        locality_histories={
            ("pica", "Water Content"): ("z6-29235", documents)
        }
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/localidades/pica/lecturas/historial",
            params={
                "variable": "Water Content",
                "horas": 24,
                "puntos": 10,
                "suavizado": "true",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["localidad"] == "pica"
    assert body["device_sn"] == "z6-29235"
    assert body["variable"] == "Water Content"
    assert body["units"] == "%"
    assert body["range"] == {"hours": 24, "points_requested": 10}
    assert body["count"] == 10
    assert body["items"][0] == {
        "datetime": "2023-11-14T22:13:20+00:00",
        "timestamp_utc": 1_700_000_000,
        "value": 0.0,
    }
    assert body["items"][-1] == {
        "datetime": "2023-11-14T22:32:20+00:00",
        "timestamp_utc": 1_700_001_140,
        "value": 19.0,
    }
    assert all(item["value"] is not None for item in body["items"])
    assert [item["timestamp_utc"] for item in body["items"]] == sorted(
        item["timestamp_utc"] for item in body["items"]
    )
    assert database.history_calls[0][:2] == ("pica", "Water Content")


def test_locality_history_without_device_returns_empty_series() -> None:
    database = FakeMongoDatabase(
        locality_histories={
            ("huayquique", "Air Temperature"): (None, [])
        }
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/localidades/huayquique/lecturas/historial",
            params={"variable": "Air Temperature"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "localidad": "huayquique",
        "device_sn": None,
        "variable": "Air Temperature",
        "units": None,
        "range": {"hours": 24, "points_requested": 60},
        "count": 0,
        "items": [],
    }


def test_locality_history_validates_required_variable_and_point_limits() -> None:
    with TestClient(build_test_app(FakeMongoDatabase())) as client:
        missing_variable = client.get(
            "/api/v1/localidades/pica/lecturas/historial"
        )
        too_few_points = client.get(
            "/api/v1/localidades/pica/lecturas/historial",
            params={"variable": "VPD", "puntos": 9},
        )
        too_many_points = client.get(
            "/api/v1/localidades/pica/lecturas/historial",
            params={"variable": "VPD", "puntos": 301},
        )

    assert missing_variable.status_code == 422
    assert too_few_points.status_code == 422
    assert too_many_points.status_code == 422


def test_read_only_endpoints_return_503_when_mongodb_is_unavailable() -> None:
    database = FakeMongoDatabase(available=False)

    with TestClient(build_test_app(database)) as client:
        collection_response = client.get("/api/v1/colegios")
        latest_response = client.get("/api/v1/lecturas/ultima")

    assert collection_response.status_code == 503
    assert latest_response.status_code == 503


def test_latest_reading_falls_back_to_datetime_sort() -> None:
    fallback_document = {"_id": ObjectId(), "datetime": "2026-08-30"}

    class FakeReadingsCollection:
        def __init__(self) -> None:
            self.calls: list[tuple[dict, list[tuple[str, int]]]] = []

        async def find_one(self, query, sort):
            self.calls.append((query, sort))
            if "timestamp_utc" in query:
                return None
            return fallback_document

    class FakeMotorDatabase:
        def __init__(self, readings) -> None:
            self.readings = readings

        def __getitem__(self, collection_name: str):
            assert collection_name == "lecturas"
            return self.readings

    readings = FakeReadingsCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(readings)  # type: ignore[assignment]

    result = asyncio.run(database.latest_reading())

    assert result == fallback_document
    assert readings.calls == [
        (
            {"timestamp_utc": {"$exists": True}},
            [("timestamp_utc", DESCENDING)],
        ),
        (
            {"datetime": {"$exists": True}},
            [("datetime", DESCENDING)],
        ),
    ]


def test_locality_query_uses_exact_device_and_timestamp_sort() -> None:
    latest_document = {"_id": ObjectId(), "device_sn": "z6-28108"}

    class FakeReadingsCollection:
        def __init__(self) -> None:
            self.calls: list[tuple[dict, list[tuple[str, int]]]] = []

        async def find_one(self, query, sort):
            self.calls.append((query, sort))
            return latest_document

    class FakeMotorDatabase:
        def __init__(self, readings) -> None:
            self.readings = readings

        def __getitem__(self, collection_name: str):
            assert collection_name == "lecturas"
            return self.readings

    readings = FakeReadingsCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(readings)  # type: ignore[assignment]

    result = asyncio.run(database.latest_reading_by_locality("la-tirana"))

    assert result == latest_document
    assert readings.calls == [
        (
            {"device_sn": "z6-28108"},
            [("timestamp_utc", DESCENDING)],
        )
    ]


def test_locality_summary_pipeline_gets_latest_document_per_variable() -> None:
    documents = [
        {"variable": "Water Content", "value": 31.2},
        {"variable": "Soil Temperature", "value": 18.4},
    ]

    class FakeAggregateCursor:
        async def to_list(self, length: int):
            assert length == 100
            return documents

    class FakeReadingsCollection:
        def __init__(self) -> None:
            self.pipeline = None
            self.hint = None

        def aggregate(self, pipeline, hint):
            self.pipeline = pipeline
            self.hint = hint
            return FakeAggregateCursor()

    class FakeMotorDatabase:
        def __init__(self, readings) -> None:
            self.readings = readings

        def __getitem__(self, collection_name: str):
            assert collection_name == "lecturas"
            return self.readings

    readings = FakeReadingsCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(readings)  # type: ignore[assignment]

    result = asyncio.run(
        database.latest_readings_summary_by_locality("colchane")
    )

    assert result == ("z6-28148", documents)
    assert readings.pipeline == [
        {"$match": {"device_sn": "z6-28148"}},
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
    assert readings.hint == "device_sn_variable_timestamp_utc_desc"


def test_history_query_uses_time_filter_ascending_sort_and_index() -> None:
    documents = [
        {"timestamp_utc": 1_700_000_000, "value": 20.5, "units": "°C"}
    ]

    class FakeHistoryCursor:
        def __init__(self) -> None:
            self.sort_call = None
            self.hint_name = None
            self.position = 0

        def sort(self, field, direction):
            self.sort_call = (field, direction)
            return self

        def hint(self, name):
            self.hint_name = name
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.position >= len(documents):
                raise StopAsyncIteration
            document = documents[self.position]
            self.position += 1
            return document

    class FakeReadingsCollection:
        def __init__(self) -> None:
            self.query = None
            self.projection = None
            self.cursor = FakeHistoryCursor()

        def find(self, query, projection):
            self.query = query
            self.projection = projection
            return self.cursor

    class FakeMotorDatabase:
        def __init__(self, readings) -> None:
            self.readings = readings

        def __getitem__(self, collection_name: str):
            assert collection_name == "lecturas"
            return self.readings

    readings = FakeReadingsCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(readings)  # type: ignore[assignment]

    result = asyncio.run(
        database.readings_history_by_locality(
            "pica",
            "Soil Temperature",
            1_699_913_600,
        )
    )

    assert result == ("z6-29235", documents)
    assert readings.query == {
        "device_sn": "z6-29235",
        "variable": "Soil Temperature",
        "timestamp_utc": {"$gte": 1_699_913_600},
        "value": {"$ne": None},
    }
    assert readings.cursor.sort_call == ("timestamp_utc", ASCENDING)
    assert readings.cursor.hint_name == "device_sn_variable_timestamp_utc_desc"


def test_save_daily_plant_measurements_builds_upsert_documents() -> None:
    database = FakeMongoDatabase(
        plant_upsert_result={"created": 1, "updated": 1}
    )
    payload = {
        "localidad": "Píca",
        "fecha": "2026-09-02",
        "ciclo_id": "ciclo-2026",
        "colegio_id": "school-008",
        "huerto_id": "huerto-01",
        "observacion": "Medición de la mañana",
        "mediciones": [
            {
                "planta_numero": 1,
                "altura_cm": 12.5,
            },
            {
                "planta_numero": 2,
                "altura_cm": 13.5,
            },
        ],
    }

    with TestClient(build_test_app(database)) as client:
        response = client.post("/api/v1/mediciones-plantas", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "localidad": "pica",
        "fecha": "2026-09-02",
        "ciclo_id": "ciclo-2026",
        "count": 2,
        "created": 1,
        "updated": 1,
    }
    documents = database.plant_upsert_calls[0]
    assert [item["planta_numero"] for item in documents] == [1, 2]
    assert [item["altura_cm"] for item in documents] == [12.5, 13.5]
    assert all("largo_hoja_cm" not in item for item in documents)
    assert all("ancho_hoja_cm" not in item for item in documents)
    assert all(item["localidad"] == "pica" for item in documents)
    assert all(item["observacion"] == "Medición de la mañana" for item in documents)
    assert all(isinstance(item["updated_at"], datetime) for item in documents)


def test_save_daily_plant_measurements_validates_heights_and_duplicates() -> None:
    database = FakeMongoDatabase()
    base_payload = {
        "localidad": "pica",
        "fecha": "2026-09-02",
        "mediciones": [
            {
                "planta_numero": 1,
                "altura_cm": 0,
            }
        ],
    }
    duplicate_payload = {
        **base_payload,
        "mediciones": [
            {
                "planta_numero": 1,
                "altura_cm": 12,
            },
            {
                "planta_numero": 1,
                "altura_cm": 13,
            },
        ],
    }

    with TestClient(build_test_app(database)) as client:
        invalid_height = client.post(
            "/api/v1/mediciones-plantas",
            json=base_payload,
        )
        duplicate_plant = client.post(
            "/api/v1/mediciones-plantas",
            json=duplicate_payload,
        )

    assert invalid_height.status_code == 422
    assert duplicate_plant.status_code == 422
    assert database.plant_upsert_calls == []


def test_get_daily_plant_measurements_returns_heights() -> None:
    database = FakeMongoDatabase(
        plant_measurements=[
            {
                "planta_numero": 1,
                "altura_cm": 10.0,
                "observacion": "Buen estado",
            },
            {
                "planta_numero": 2,
                "altura_cm": 12.0,
                "observacion": "Buen estado",
            },
        ]
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-plantas",
            params={"localidad": "pica", "fecha": "2026-09-02"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "localidad": "pica",
        "fecha": "2026-09-02",
        "ciclo_id": "general",
        "count": 2,
        "items": [
            {
                "planta_numero": 1,
                "altura_cm": 10.0,
                "observacion": "Buen estado",
            },
            {
                "planta_numero": 2,
                "altura_cm": 12.0,
                "observacion": "Buen estado",
            },
        ],
    }
    assert database.plant_measurement_calls == [
        ("pica", "2026-09-02", "general")
    ]


def test_get_daily_plant_measurements_validates_date() -> None:
    database = FakeMongoDatabase()

    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-plantas",
            params={"localidad": "pica", "fecha": "02-09-2026"},
        )

    assert response.status_code == 422
    assert database.plant_measurement_calls == []


def test_daily_plant_averages_returns_last_30_days() -> None:
    database = FakeMongoDatabase(
        plant_averages=[
            {
                "fecha": "2026-09-01",
                "altura_promedio_cm": 12.345,
                "plantas_medidas": 20,
            },
            {
                "fecha": "2026-09-02",
                "altura_promedio_cm": 13.1,
                "plantas_medidas": 18,
            },
        ]
    )

    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-plantas/promedio",
            params={"localidad": "pica", "dias": 30},
        )

    assert response.status_code == 200
    assert response.json() == {
        "localidad": "pica",
        "count": 2,
        "items": [
            {
                "fecha": "2026-09-01",
                "altura_promedio_cm": 12.35,
                "plantas_medidas": 20,
            },
            {
                "fecha": "2026-09-02",
                "altura_promedio_cm": 13.1,
                "plantas_medidas": 18,
            },
        ],
    }
    expected_since = (
        datetime.now(timezone.utc).date() - timedelta(days=29)
    ).isoformat()
    assert database.plant_average_calls == [("pica", expected_since)]


def test_plant_measurements_return_503_when_mongodb_is_unavailable() -> None:
    database = FakeMongoDatabase(available=False)

    with TestClient(build_test_app(database)) as client:
        post_response = client.post(
            "/api/v1/mediciones-plantas",
            json={
                "localidad": "pica",
                "fecha": "2026-09-02",
                "mediciones": [
                    {
                        "planta_numero": 1,
                        "altura_cm": 12,
                    }
                ],
            },
        )
        get_response = client.get(
            "/api/v1/mediciones-plantas/promedio",
            params={"localidad": "pica"},
        )
        daily_response = client.get(
            "/api/v1/mediciones-plantas",
            params={"localidad": "pica", "fecha": "2026-09-02"},
        )

    assert post_response.status_code == 503
    assert get_response.status_code == 503
    assert daily_response.status_code == 503


def test_plant_measurement_upsert_uses_unique_selector_and_indexes() -> None:
    class UpdateResult:
        def __init__(self, upserted_id):
            self.upserted_id = upserted_id

    class FakePlantCollection:
        def __init__(self) -> None:
            self.indexes = []
            self.updates = []

        async def create_index(self, keys, name, unique=False, **kwargs):
            self.indexes.append((keys, name, unique))

        async def update_one(self, selector, update, upsert):
            self.updates.append((selector, update, upsert))
            return UpdateResult("new-id" if len(self.updates) == 1 else None)

    class FakeMotorDatabase:
        def __init__(self, collection) -> None:
            self.collection = collection

        def __getitem__(self, collection_name: str):
            assert collection_name == "mediciones_plantas"
            return self.collection

    collection = FakePlantCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(collection)  # type: ignore[assignment]
    timestamp = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    documents = [
        {
            "localidad": "pica",
            "ciclo_id": "general",
            "fecha": "2026-09-02",
            "planta_numero": number,
            "altura_cm": 10.0 + number,
            "updated_at": timestamp,
        }
        for number in (1, 2)
    ]

    result = asyncio.run(database.upsert_plant_measurements(documents))

    assert result == {"created": 1, "updated": 1}
    assert collection.indexes[0][1:] == (PLANT_LOCALITY_DATE_INDEX, False)
    assert collection.indexes[1][1:] == (
        PLANT_UNIQUE_MEASUREMENT_INDEX,
        True,
    )
    assert collection.updates[0][0] == {
        "localidad": "pica",
        "ciclo_id": "general",
        "fecha": "2026-09-02",
        "planta_numero": 1,
    }
    assert collection.updates[0][2] is True
    assert collection.updates[0][1]["$setOnInsert"] == {
        "created_at": timestamp
    }


def test_plant_averages_filter_invalid_heights_and_sort_by_date() -> None:
    class FakeAggregateCursor:
        async def to_list(self, length):
            assert length == 365
            return []

    class FakePlantCollection:
        def __init__(self) -> None:
            self.pipeline = None

        def aggregate(self, pipeline):
            self.pipeline = pipeline
            return FakeAggregateCursor()

    class FakeMotorDatabase:
        def __init__(self, collection) -> None:
            self.collection = collection

        def __getitem__(self, collection_name: str):
            assert collection_name == "mediciones_plantas"
            return self.collection

    collection = FakePlantCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(collection)  # type: ignore[assignment]

    result = asyncio.run(
        database.plant_measurement_averages("pica", "2026-08-04")
    )

    assert result == []
    assert collection.pipeline[0] == {
        "$match": {
            "localidad": "pica",
            "fecha": {"$gte": "2026-08-04"},
            "altura_cm": {"$type": "number", "$gt": 0},
        }
    }
    assert collection.pipeline[2] == {"$sort": {"_id": ASCENDING}}


@pytest.mark.parametrize(
    ("locality", "serial", "filename"),
    [
        ("pica", "GA05440096", "Pica 7 de julio a 6 de Agosto(2).CSV"),
        ("colchane", "GA06130059", "Colchane 13 de julio a 12 de Agosto(2).CSV"),
        ("huara", "GA04460088", "Huara 6 de julio a 5 de Agosto(2).CSV"),
        ("huara", "GA04460088", "Huara 11 de Mayo a 10 de Junio(2).CSV"),
    ],
)
def test_import_hanna_csv_detects_metadata_and_invalid_rows(
    locality: str,
    serial: str,
    filename: str,
) -> None:
    database = FakeMongoDatabase(
        hanna_upsert_results=[{"created": 2, "updated": 0}]
    )
    with TestClient(build_test_app(database)) as client:
        response = client.post(
            "/api/v1/mediciones-hanna/importar-csv",
            data={"localidad": locality},
            files={"archivo": (filename, build_hanna_csv(serial), "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["equipo_modelo"] == "HI981420"
    assert body["equipo_serial"] == serial
    assert body["instrument_id"] == "0003"
    assert body["registros_leidos"] == 2
    assert body["validos"] == 1
    assert body["invalidos"] == 1
    assert body["duplicados"] == 0
    assert body["variables_detectadas"] == [
        "pH",
        "conductividad eléctrica",
        "temperatura",
    ]
    invalid_document = database.hanna_upsert_calls[0][1]
    assert invalid_document["valido"] is False
    assert invalid_document["motivos_alerta"] == [
        "marca !!",
        "pH fuera de rango",
        "temperatura sospechosa",
    ]
    assert invalid_document["datetime_local"] == "2026-07-08T14:33:42"


def test_importing_same_hanna_file_updates_instead_of_duplicating() -> None:
    database = FakeMongoDatabase(
        hanna_upsert_results=[
            {"created": 2, "updated": 0},
            {"created": 0, "updated": 2},
        ]
    )
    upload = {
        "data": {"localidad": "pica"},
        "files": {
            "archivo": (
                "Pica.CSV",
                build_hanna_csv("GA05440096"),
                "text/csv",
            )
        },
    }
    with TestClient(build_test_app(database)) as client:
        first = client.post(
            "/api/v1/mediciones-hanna/importar-csv",
            **upload,
        )
        second = client.post(
            "/api/v1/mediciones-hanna/importar-csv",
            **upload,
        )

    assert first.json()["insertados"] == 2
    assert first.json()["actualizados"] == 0
    assert second.json()["insertados"] == 0
    assert second.json()["actualizados"] == 2
    assert second.json()["duplicados"] == 2
    assert len(database.hanna_upsert_calls) == 2


def test_hanna_missing_header_error_includes_clean_diagnostic_lines() -> None:
    content = b"Model;HI981420\x00\r\nSerial #;GA05440096\x00\r\nSin tabla\x00"

    with pytest.raises(HannaCSVError) as error:
        parse_hanna_csv(content, "sin-tabla.CSV")

    message = str(error.value)
    assert "Primeras 30 líneas limpias" in message
    assert "01: Model;HI981420" in message
    assert "02: Serial #;GA05440096" in message
    assert "\x00" not in message


def test_hanna_summary_endpoint() -> None:
    last_upload = datetime(2026, 8, 12, 18, 30, tzinfo=timezone.utc)
    database = FakeMongoDatabase(
        hanna_summary={
            "ultima_carga": last_upload,
            "archivos_cargados": 2,
            "total_registros": 100,
            "total_validos": 74,
            "total_invalidos": 26,
            "fecha_minima": "2026-07-07",
            "fecha_maxima": "2026-08-12",
            "equipo_serial": "GA05440096",
        }
    )
    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-hanna/resumen",
            params={"localidad": "pica"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "localidad": "pica",
        "ultima_carga": "2026-08-12T18:30:00Z",
        "archivos_cargados": 2,
        "total_registros": 100,
        "total_validos": 74,
        "total_invalidos": 26,
        "fecha_minima": "2026-07-07",
        "fecha_maxima": "2026-08-12",
        "equipo_serial": "GA05440096",
    }
    assert database.hanna_summary_calls == ["pica"]


def test_hanna_temperature_series_endpoint_returns_daily_water_values() -> None:
    database = FakeMongoDatabase(
        hanna_temperature_series=[
            {"fecha": "2026-07-07", "valor": 24.456},
            {"fecha": "2026-07-08", "valor": 25.1},
        ]
    )
    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-hanna/series",
            params={"localidad": "pica", "variable": "temperatura", "dias": 7},
        )

    assert response.status_code == 200
    assert response.json() == {
        "localidad": "pica",
        "variable": "temperatura_agua",
        "nombre": "Temperatura del agua del estanque",
        "unidad": "°C",
        "items": [
            {"fecha": "2026-07-07", "valor": 24.46},
            {"fecha": "2026-07-08", "valor": 25.1},
        ],
    }
    assert database.hanna_temperature_series_calls == [("pica", 7)]


def test_latest_hanna_temperature_endpoint_returns_real_water_value() -> None:
    database = FakeMongoDatabase(
        latest_hanna_temperature={
            "temp_avg_c": 24.456,
            "fecha": "2026-08-06",
            "hora": "14:30:00",
            "datetime_local": "2026-08-06T14:30:00",
        }
    )
    database.hanna_dataloggers["GA05440096"] = {
        "serial_hanna": "GA05440096",
        "modelo": "HI981420",
        "instrument_id": "0003",
        "colegio_id": "school-pica",
        "localidad": "pica",
    }
    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-hanna/ultima",
            params={"localidad": "pica", "variable": "temperatura"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "colegio_id": "school-pica",
        "localidad": "pica",
        "variable": "temperatura_agua",
        "nombre": "Temperatura del agua del estanque",
        "valor": 24.46,
        "unidad": "°C",
        "fecha": "2026-08-06",
        "hora": "14:30:00",
        "datetime_local": "2026-08-06T14:30:00",
        "mensaje": None,
        "fuente": "hanna",
        "serial_hanna": "GA05440096",
        "modelo": "HI981420",
        "instrument_id": "0003",
        "estado": "ok",
    }
    assert database.latest_hanna_field_calls == [("school-pica", "temp_avg_c")]


def test_latest_hanna_temperature_endpoint_returns_friendly_empty_state() -> None:
    database = FakeMongoDatabase()
    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-hanna/ultima",
            params={"localidad": "huayquique", "variable": "temperatura"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "colegio_id": "school-huayquique",
        "localidad": "huayquique",
        "variable": "temperatura_agua",
        "nombre": "Temperatura del agua del estanque",
        "valor": None,
        "unidad": "°C",
        "fecha": None,
        "hora": None,
        "datetime_local": None,
        "mensaje": "Este huerto no tiene un equipo Hanna asociado",
        "fuente": "hanna",
        "serial_hanna": None,
        "modelo": None,
        "instrument_id": None,
        "estado": "sin_equipo_hanna",
    }


@pytest.mark.parametrize(
    ("query_variable", "expected_key", "field", "value", "unit"),
    [
        ("ph", "ph_agua", "ph_avg", 7.08, "pH"),
        ("conductividad", "sales_agua", "ec_avg_ms_cm", 1.17, "mS/cm"),
    ],
)
def test_latest_hanna_endpoint_supports_ph_and_conductivity(
    query_variable, expected_key, field, value, unit
) -> None:
    database = FakeMongoDatabase(
        latest_hanna_temperature={
            field: value,
            "fecha": "2026-08-12",
            "hora": "14:52:47",
            "datetime_local": "2026-08-12T14:52:47",
        }
    )
    database.hanna_dataloggers["GA06130059"] = {
        "serial_hanna": "GA06130059",
        "modelo": "HI981420",
        "instrument_id": "0005",
        "colegio_id": "school-colchane",
        "localidad": "colchane",
    }
    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-hanna/ultima",
            params={"localidad": "colchane", "variable": query_variable},
        )

    assert response.status_code == 200
    assert response.json()["variable"] == expected_key
    assert response.json()["valor"] == value
    assert response.json()["unidad"] == unit
    assert response.json()["serial_hanna"] == "GA06130059"
    assert database.latest_hanna_field_calls == [("school-colchane", field)]


@pytest.mark.parametrize(
    ("document", "expected_state", "expected_message"),
    [
        (None, "sin_datos", "Equipo Hanna asociado, pero sin mediciones cargadas"),
        ({"temp_avg_c": None}, "sin_datos_validos", "No hay una medición válida para esta variable"),
    ],
)
def test_latest_hanna_endpoint_distinguishes_missing_and_invalid_measurements(
    document, expected_state, expected_message
) -> None:
    database = FakeMongoDatabase(latest_hanna_temperature=document)
    database.hanna_dataloggers["GA00000001"] = {
        "serial_hanna": "GA00000001",
        "modelo": "HI981420",
        "instrument_id": "0099",
        "colegio_id": "school-pica",
        "localidad": "pica",
    }
    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-hanna/ultima",
            params={"localidad": "pica", "variable": "temperatura"},
        )

    assert response.status_code == 200
    assert response.json()["estado"] == expected_state
    assert response.json()["mensaje"] == expected_message
    assert response.json()["serial_hanna"] == "GA00000001"


def test_latest_hanna_temperature_uses_valid_collection_records_only() -> None:
    class FakeHannaCollection:
        def __init__(self) -> None:
            self.query = None
            self.projection = None
            self.sort = None

        async def find_one(self, query, projection, sort):
            self.query = query
            self.projection = projection
            self.sort = sort
            return {"temp_avg_c": 20.5}

    class FakeMotorDatabase:
        def __init__(self, collection) -> None:
            self.collection = collection

        def __getitem__(self, collection_name: str):
            assert collection_name == "mediciones_hanna"
            return self.collection

    collection = FakeHannaCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(collection)  # type: ignore[assignment]

    result = asyncio.run(database.latest_hanna_temperature("pica"))

    assert result == {"temp_avg_c": 20.5}
    assert collection.query == {
        "localidad": "pica",
        "valido": True,
        "temp_avg_c": {"$type": "number", "$gt": 0, "$lt": 50},
    }
    assert collection.sort == [("datetime_local", DESCENDING)]
    assert "timestamp_utc" not in collection.projection


def test_latest_hanna_field_uses_all_college_serials_valid_rows_and_real_field() -> None:
    class EquipmentCursor:
        async def to_list(self, length):
            assert length == 1000
            return [
                {"serial_hanna": "OLD", "modelo": "HI981420", "instrument_id": "0001", "estado": "reemplazado"},
                {"serial_hanna": "NEW", "modelo": "HI981420", "instrument_id": "0002", "estado": "activo"},
            ]

    class EquipmentCollection:
        def find(self, query, projection):
            assert query == {"colegio_id": "college-pica"}
            return EquipmentCursor()

    class MeasurementCollection:
        def __init__(self):
            self.valid_query = None

        async def find_one(self, query, projection, sort=None):
            if sort is None:
                assert "$or" in query
                return {"_id": ObjectId()}
            self.valid_query = query
            assert sort == [("datetime_local", DESCENDING)]
            return {
                "serial_hanna": "OLD",
                "ph_avg": 7.19,
                "datetime_local": "2026-08-01T08:25:36",
            }

    class FakeMotorDatabase:
        def __init__(self):
            self.measurements = MeasurementCollection()

        def __getitem__(self, name):
            return EquipmentCollection() if name == "dataloggers_hanna" else self.measurements

    motor = FakeMotorDatabase()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = motor  # type: ignore[assignment]

    result = asyncio.run(database.latest_hanna_field_for_college("college-pica", "ph_avg"))

    assert result["estado"] == "ok"
    assert result["serial_hanna"] == "OLD"
    assert result["instrument_id"] == "0001"
    assert motor.measurements.valid_query == {
        "$or": [
            {"serial_hanna": {"$in": ["OLD", "NEW"]}},
            {"equipo_serial": {"$in": ["OLD", "NEW"]}},
        ],
        "valido": True,
        "ph_avg": {"$type": "number"},
    }
    assert "localidad" not in motor.measurements.valid_query


@pytest.mark.parametrize(
    ("equipment", "has_measurements", "valid_document", "expected_state"),
    [
        ([], False, None, "sin_equipo_hanna"),
        ([{"serial_hanna": "ONE", "estado": "activo"}], False, None, "sin_datos"),
        ([{"serial_hanna": "ONE", "estado": "activo"}], True, None, "sin_datos_validos"),
    ],
)
def test_latest_hanna_field_distinguishes_empty_states(
    equipment, has_measurements, valid_document, expected_state
) -> None:
    class Cursor:
        async def to_list(self, length):
            return equipment

    class EquipmentCollection:
        def find(self, query, projection):
            return Cursor()

    class MeasurementCollection:
        async def find_one(self, query, projection, sort=None):
            return ({"_id": ObjectId()} if has_measurements else None) if sort is None else valid_document

    class FakeMotorDatabase:
        def __getitem__(self, name):
            return EquipmentCollection() if name == "dataloggers_hanna" else MeasurementCollection()

    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase()  # type: ignore[assignment]

    result = asyncio.run(database.latest_hanna_field_for_college("college-empty", "ec_avg_ms_cm"))

    assert result["estado"] == expected_state


def test_hanna_temperature_series_returns_empty_items_without_data() -> None:
    database = FakeMongoDatabase()
    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-hanna/series",
            params={"localidad": "huara", "variable": "temperatura", "dias": 7},
        )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_hanna_series_rejects_variables_not_enabled_for_school_frontend() -> None:
    database = FakeMongoDatabase()
    with TestClient(build_test_app(database)) as client:
        response = client.get(
            "/api/v1/mediciones-hanna/series",
            params={"localidad": "pica", "variable": "ph", "dias": 7},
        )

    assert response.status_code == 422
    assert database.hanna_temperature_series_calls == []


def test_hanna_temperature_series_uses_valid_hanna_records_only() -> None:
    class FakeAggregateCursor:
        async def to_list(self, length):
            assert length == 7
            return [
                {"fecha": "2026-08-05", "valor": 24.5},
                {"fecha": "2026-08-06", "valor": 25.1},
            ]

    class FakeHannaCollection:
        def __init__(self) -> None:
            self.find_filter = None
            self.find_sort = None
            self.pipeline = None

        async def find_one(self, query, projection, sort):
            self.find_filter = query
            self.find_sort = sort
            assert projection == {"_id": 0, "fecha": 1}
            return {"fecha": "2026-08-06"}

        def aggregate(self, pipeline):
            self.pipeline = pipeline
            return FakeAggregateCursor()

    class FakeMotorDatabase:
        def __init__(self, collection) -> None:
            self.collection = collection

        def __getitem__(self, collection_name: str):
            assert collection_name == "mediciones_hanna"
            return self.collection

    collection = FakeHannaCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(collection)  # type: ignore[assignment]

    result = asyncio.run(database.hanna_daily_temperature_series("pica", 7))

    assert result[-1] == {"fecha": "2026-08-06", "valor": 25.1}
    assert collection.find_filter == {
        "localidad": "pica",
        "valido": True,
        "temp_avg_c": {"$type": "number", "$gt": 0, "$lt": 50},
    }
    assert collection.find_sort == [("fecha", DESCENDING)]
    assert collection.pipeline[0]["$match"]["fecha"] == {
        "$gte": "2026-07-31",
        "$lte": "2026-08-06",
    }
    assert collection.pipeline[1] == {
        "$group": {"_id": "$fecha", "valor": {"$avg": "$temp_avg_c"}}
    }
    assert collection.pipeline[2] == {"$sort": {"_id": ASCENDING}}


def test_hanna_indexes_and_unique_upsert_selector() -> None:
    class BulkResult:
        upserted_count = 1
        matched_count = 1

    class FakeHannaCollection:
        def __init__(self) -> None:
            self.indexes = []
            self.operations = []

        async def create_index(self, keys, name, unique=False, **kwargs):
            self.indexes.append((keys, name, unique))

        async def bulk_write(self, operations, ordered):
            self.operations = operations
            assert ordered is False
            return BulkResult()

    class FakeMotorDatabase:
        def __init__(self, collection) -> None:
            self.collection = collection

        def __getitem__(self, collection_name: str):
            assert collection_name == "mediciones_hanna"
            return self.collection

    collection = FakeHannaCollection()
    database = MongoDatabase(Settings(_env_file=None))
    database._database = FakeMotorDatabase(collection)  # type: ignore[assignment]
    timestamp = datetime(2026, 8, 12, 18, 30, tzinfo=timezone.utc)
    documents = [
        {
            "localidad": "pica",
            "equipo_serial": "GA05440096",
            "datetime_local": f"2026-07-0{day}T14:33:42",
            "updated_at": timestamp,
        }
        for day in (7, 8)
    ]

    result = asyncio.run(database.upsert_hanna_measurements(documents))

    assert result == {"created": 1, "updated": 1}
    assert [item[1] for item in collection.indexes] == [
        HANNA_LOCALITY_DATE_INDEX,
        HANNA_UNIQUE_MEASUREMENT_INDEX,
        HANNA_LOCALITY_VALID_INDEX,
        "hanna_serial_datetime_unique",
    ]
    assert collection.indexes[1][2] is True
    assert collection.operations[0]._filter == {
        "datetime_local": "2026-07-07T14:33:42",
        "$or": [
            {"serial_hanna": "GA05440096"},
            {"equipo_serial": "GA05440096"},
        ],
    }
    assert collection.operations[0]._upsert is True


def test_settings_are_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setenv("MONGODB_DATABASE", "huerto2027_test")
    monkeypatch.setenv("MONGODB_TIMEOUT_MS", "5000")
    monkeypatch.setenv("ENABLE_DIAGNOSTICS", "true")

    settings = Settings(_env_file=None)

    assert settings.app_environment == "test"
    assert settings.mongodb_database == "huerto2027_test"
    assert settings.mongodb_timeout_ms == 5000
    assert settings.enable_diagnostics is True
