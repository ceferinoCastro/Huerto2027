import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.mongodb import MongoDatabase
from app.main import create_app
from app.services.domain import DomainConflictError, DomainNotFoundError
from app.services.sensor_associations import (
    applicable_proposals,
    build_initial_association_proposal,
)


def inventory():
    return {
        "colegios": [{"_id": "pica-id", "nombre": "Colegio Pica"}],
        "dataloggers": [{"modelo": "z6-real", "ubicacion": "Colegio Pica"}],
        "sensores": [
            {"sensor_sn": "T12-1", "sensor_name": "TEROS 12", "ubicacion_fisica": "Cama cultivo 1"},
            {"sensor_sn": "T21-1", "sensor_name": "TEROS 21", "ubicacion_fisica": "Sector raíz profunda"},
        ],
        "lecturas": [
            {"device_sn": "z6-real", "sensor_sn": "ATMOS-1", "sensor_name": "ATMOS 14", "variable": "Air Temperature", "units": "°C", "count": 20, "last_ts": 20, "last_dt": "2026-08-01"},
            {"device_sn": "z6-real", "sensor_sn": "ATMOS-1", "sensor_name": "ATMOS 14", "variable": "Percent Relative Humidity", "units": "%", "count": 18, "last_ts": 18, "last_dt": "2026-08-01"},
            {"device_sn": "z6-real", "sensor_sn": "T12-1", "sensor_name": "TEROS 12", "variable": "Soil Temperature", "units": "°C", "count": 30, "last_ts": 30, "last_dt": "2026-08-02"},
            {"device_sn": "z6-real", "sensor_sn": "T12-1", "sensor_name": "TEROS 12", "variable": "Water Content", "units": "m³/m³", "count": 30, "last_ts": 30, "last_dt": "2026-08-02"},
            {"device_sn": "z6-real", "sensor_sn": "T21-1", "sensor_name": "TEROS 21", "variable": "Soil Temperature", "units": "°C", "count": 25, "last_ts": 25, "last_dt": "2026-08-01"},
        ],
        "hanna": [{"serial_hanna": "KNOWN", "count": 10, "last": "2026-08-03"}],
        "dataloggers_hanna": [],
        "asociaciones": [],
    }


def by_key(items, key):
    return next(item for item in items if item["clave_educativa"] == key)


def test_proposal_uses_real_device_readings_and_keeps_missing_variables_pending():
    proposal = build_initial_association_proposal(inventory())
    assert len(proposal) == 11
    assert by_key(proposal, "temperatura_aire")["sensor_sn"] == "ATMOS-1"
    assert by_key(proposal, "humedad_tierra")["unidad"] == "m³/m³"
    assert by_key(proposal, "humedad_aire")["sensor_sn"] == "ATMOS-1"
    assert by_key(proposal, "humedad_aire")["unidad"] == "%"
    assert by_key(proposal, "humedad_hojas")["estado_asociacion"] == "pendiente"
    assert by_key(proposal, "temperatura_tierra")["confianza"] == "alta"
    assert by_key(proposal, "temperatura_bajo_tierra")["confianza"] == "alta"


def test_proposal_accepts_legacy_relative_humidity_alias():
    data = inventory()
    data["lecturas"] = [
        item for item in data["lecturas"] if item["variable"] != "Percent Relative Humidity"
    ] + [
        {"device_sn": "z6-real", "sensor_sn": "ATMOS-1", "sensor_name": "ATMOS 14", "variable": "Relative Humidity", "units": "%", "count": 15, "last_ts": 15, "last_dt": "2026-08-01"},
    ]
    proposal = build_initial_association_proposal(data)
    assert by_key(proposal, "humedad_aire")["sensor_sn"] == "ATMOS-1"
    assert by_key(proposal, "humedad_aire")["variable_tecnica"] == "Percent Relative Humidity"


def test_hanna_requires_an_existing_college_assignment():
    data = inventory()
    pending = build_initial_association_proposal(data)
    assert by_key(pending, "temperatura_agua")["estado_asociacion"] == "pendiente"
    data["dataloggers_hanna"] = [{"serial_hanna": "KNOWN", "colegio_id": "pica-id"}]
    associated = build_initial_association_proposal(data)
    assert by_key(associated, "temperatura_agua")["sensor_sn"] == "KNOWN"
    assert by_key(associated, "temperatura_agua")["source"] == "hanna"


def test_manual_variables_have_no_sensor_and_pending_rows_are_not_applicable():
    proposal = build_initial_association_proposal(inventory())
    manual = by_key(proposal, "altura_planta")
    assert manual["source"] == "manual"
    assert manual["device_sn"] is None
    assert manual["sensor_sn"] is None
    assert all(item["confianza"] != "pendiente" for item in applicable_proposals(proposal))


class AssociationDatabase:
    def __init__(self):
        self.items = {}
        self.connected = False

    async def connect(self): self.connected = True
    def close(self): self.connected = False
    async def list_sensor_associations(self, locality):
        return [item for item in self.items.values() if item["localidad"] == locality]
    async def create_sensor_association(self, data):
        identifier = "64f000000000000000000001"
        item = {"_id": identifier, **data, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
        self.items[identifier] = item
        return item
    async def update_sensor_association(self, identifier, data):
        if identifier not in self.items: raise DomainNotFoundError("Asociación no encontrada")
        self.items[identifier].update(data)
        return self.items[identifier]
    async def delete_sensor_association(self, identifier):
        if identifier not in self.items: raise DomainNotFoundError("Asociación no encontrada")
        del self.items[identifier]


def test_association_crud_contract_used_by_frontend2():
    database = AssociationDatabase()
    app = create_app(Settings(_env_file=None), database)
    payload = {
        "localidad": "pica",
        "colegio_id": "pica-id",
        "device_sn": "z6-real",
        "clave_educativa": "temperatura_aire",
        "sensor_sn": "ATMOS-1",
        "variable_tecnica": "Air Temperature",
    }
    with TestClient(app) as client:
        created = client.post("/api/v1/asociaciones-sensores", json=payload)
        listed = client.get("/api/v1/asociaciones-sensores", params={"localidad": "pica"})
        updated = client.put(
            "/api/v1/asociaciones-sensores/64f000000000000000000001",
            json={**payload, "ubicacion": "Cama de cultivo 1"},
        )
        deleted = client.delete("/api/v1/asociaciones-sensores/64f000000000000000000001")
    assert created.status_code == 201
    assert listed.json()["count"] == 1
    assert updated.json()["ubicacion"] == "Cama de cultivo 1"
    assert deleted.json() == {"status": "ok", "deleted": True}


class _RaisingDatabase:
    """Mimics the real MongoDatabase raising a specific exception on save."""

    def __init__(self, exc: Exception):
        self.exc = exc
        self.connected = False

    async def connect(self): self.connected = True
    def close(self): self.connected = False
    async def create_sensor_association(self, data):
        raise self.exc
    async def update_sensor_association(self, identifier, data):
        raise self.exc


def test_create_association_returns_descriptive_409_for_business_conflict():
    database = _RaisingDatabase(
        DomainConflictError(
            "El sensor no tiene lecturas reales para esa variable técnica "
            "('Percent Relative Humidity'); verifica el sensor_sn o que el "
            "dispositivo haya reportado datos para ese sensor."
        )
    )
    app = create_app(Settings(_env_file=None), database)
    payload = {
        "localidad": "pica",
        "colegio_id": "pica-id",
        "device_sn": "z6-real",
        "clave_educativa": "humedad_aire",
        "sensor_sn": "unknown-sn",
        "variable_tecnica": "Percent Relative Humidity",
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/asociaciones-sensores", json=payload)
    assert response.status_code == 409
    assert "Percent Relative Humidity" in response.json()["detail"]
    assert response.json()["detail"] != "MongoDB no está disponible"


def test_create_association_returns_descriptive_500_for_unexpected_error():
    database = _RaisingDatabase(KeyError("colegio_id"))
    app = create_app(Settings(_env_file=None), database)
    payload = {
        "localidad": "pica",
        "colegio_id": "pica-id",
        "device_sn": "z6-real",
        "clave_educativa": "humedad_aire",
        "sensor_sn": "ATMOS-1",
        "variable_tecnica": "Percent Relative Humidity",
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/asociaciones-sensores", json=payload)
    assert response.status_code == 500
    assert "colegio_id" in response.json()["detail"]


class _FakeCollection:
    def __init__(self, documents):
        self.documents = documents
        self.queries: list[dict] = []

    async def find_one(self, query):
        self.queries.append(query)
        variable_filter = query.get("variable")
        accepted = (
            set(variable_filter["$in"]) if isinstance(variable_filter, dict) else {variable_filter}
        )
        for document in self.documents:
            if document.get("device_sn") != query.get("device_sn"):
                continue
            if document.get("sensor_sn") != query.get("sensor_sn"):
                continue
            if "variable" in query and document.get("variable") not in accepted:
                continue
            if "sensor_name" in query and document.get("sensor_name") != query.get("sensor_name"):
                continue
            return document
        return None


class _FakeAssociationsCollection:
    def __init__(self):
        self.inserted: list[dict] = []

    async def index_information(self):
        return {}

    async def drop_index(self, name):
        return None

    async def create_index(self, *args, **kwargs):
        return None

    async def insert_one(self, document):
        self.inserted.append(document)

        class _Result:
            inserted_id = "64f000000000000000000099"

        return _Result()


class _FakeDatabase:
    def __init__(self, lecturas):
        self._lecturas = _FakeCollection(lecturas)
        self._asociaciones = _FakeAssociationsCollection()

    def __getitem__(self, name):
        if name == "lecturas":
            return self._lecturas
        if name == "asociaciones_sensores":
            return self._asociaciones
        raise AssertionError(f"Colección inesperada: {name}")


def _mongo_database_for_validation(lecturas, monkeypatch):
    database = MongoDatabase(Settings(_env_file=None))
    database._database = _FakeDatabase(lecturas)

    async def fake_list_carteles(*, force_refresh: bool = False):
        return [{"_id": "humedad_aire"}]

    async def fake_college_by_id(college_id: str):
        return {"nombre": "Colegio Pica"}

    monkeypatch.setattr(database, "list_carteles", fake_list_carteles)
    monkeypatch.setattr(database, "college_by_id", fake_college_by_id)
    return database


def test_create_association_http_route_accepts_percent_relative_humidity_end_to_end(monkeypatch):
    """Full stack: HTTP route -> MongoDatabase.create_sensor_association -> validation.

    Reproduces the originally reported bug: saving an association with
    "Percent Relative Humidity" (no historical readings for that exact
    variable, only for other ATMOS 14 variables) must succeed with 201,
    not fail with a generic 503.
    """
    database = _mongo_database_for_validation(
        lecturas=[
            {"device_sn": "z6-real", "sensor_sn": "ATMOS-1", "sensor_name": "ATMOS 14", "variable": "Air Temperature", "value": 22.0},
        ],
        monkeypatch=monkeypatch,
    )
    monkeypatch.setattr(database, "connect", lambda: asyncio.sleep(0))
    monkeypatch.setattr(database, "close", lambda: None)

    app = create_app(Settings(_env_file=None), database)
    payload = {
        "localidad": "pica",
        "colegio_id": "pica-id",
        "device_sn": "z6-real",
        "clave_educativa": "humedad_aire",
        "sensor_sn": "ATMOS-1",
        "sensor_name": "ATMOS 14",
        "variable_tecnica": "Percent Relative Humidity",
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/asociaciones-sensores", json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["variable_tecnica"] == "Percent Relative Humidity"


BASE_ASSOCIATION = {
    "localidad": "pica",
    "colegio_id": "pica-id",
    "clave_educativa": "humedad_aire",
    "source": "zentra",
    "device_sn": "z6-real",
    "sensor_sn": "ATMOS-1",
    "sensor_name": "ATMOS 14",
}


def test_association_accepts_atmos_14_variable_without_prior_readings(monkeypatch):
    database = _mongo_database_for_validation(
        lecturas=[
            {"device_sn": "z6-real", "sensor_sn": "ATMOS-1", "sensor_name": "ATMOS 14", "variable": "Air Temperature", "value": 22.0},
        ],
        monkeypatch=monkeypatch,
    )
    asyncio.run(database._validate_sensor_association(
        {**BASE_ASSOCIATION, "variable_tecnica": "Percent Relative Humidity"}
    ))


def test_association_accepts_legacy_relative_humidity_reading_via_alias(monkeypatch):
    database = _mongo_database_for_validation(
        lecturas=[
            {"device_sn": "z6-real", "sensor_sn": "ATMOS-1", "sensor_name": "ATMOS 14", "variable": "Relative Humidity", "value": 55.0},
        ],
        monkeypatch=monkeypatch,
    )
    asyncio.run(database._validate_sensor_association(
        {**BASE_ASSOCIATION, "variable_tecnica": "Percent Relative Humidity"}
    ))


def test_association_rejects_unknown_variable_with_descriptive_message(monkeypatch):
    database = _mongo_database_for_validation(
        lecturas=[
            {"device_sn": "z6-real", "sensor_sn": "ATMOS-1", "sensor_name": "ATMOS 14", "variable": "Air Temperature", "value": 22.0},
        ],
        monkeypatch=monkeypatch,
    )
    with pytest.raises(DomainConflictError, match="Totally Made Up Variable"):
        asyncio.run(database._validate_sensor_association(
            {**BASE_ASSOCIATION, "variable_tecnica": "Totally Made Up Variable"}
        ))


def test_association_rejects_atmos_14_variable_when_sensor_sn_has_no_evidence(monkeypatch):
    database = _mongo_database_for_validation(
        lecturas=[],
        monkeypatch=monkeypatch,
    )
    with pytest.raises(DomainConflictError):
        asyncio.run(database._validate_sensor_association(
            {**BASE_ASSOCIATION, "variable_tecnica": "Percent Relative Humidity"}
        ))


class _StaleIndexCollection:
    """Mimics a Mongo collection whose real index drifted from what the code declares."""

    def __init__(self, stale_key, *, unique=False):
        self.stale_key = stale_key
        self.stale_unique = unique
        self.dropped: list[str] = []
        self.created: list[dict] = []

    async def index_information(self):
        return {
            "asociacion_localidad_orden": {
                "key": self.stale_key,
                "unique": self.stale_unique,
            }
        }

    async def drop_index(self, name):
        self.dropped.append(name)

    async def create_index(self, keys, name, unique=False, **kwargs):
        if name in self.dropped:
            self.created.append({"keys": keys, "name": name, "unique": unique})
            return
        # create_index without a prior drop_index would raise
        # IndexKeySpecsConflict (code 86) here in real MongoDB when the key
        # spec differs from the stale one under the same name.
        if list(keys) != list(self.stale_key):
            raise AssertionError(
                "create_index llamado sin drop_index previo para una especificación distinta"
            )
        self.created.append({"keys": keys, "name": name, "unique": unique})


def test_ensure_index_drops_and_recreates_stale_compound_index():
    database = MongoDatabase(Settings(_env_file=None))
    collection = _StaleIndexCollection(stale_key=[("localidad", 1), ("orden", 1)])

    asyncio.run(database._ensure_index(
        collection,
        [("localidad", 1)],
        name="asociacion_localidad_orden",
    ))

    assert collection.dropped == ["asociacion_localidad_orden"]
    assert collection.created == [
        {"keys": [("localidad", 1)], "name": "asociacion_localidad_orden", "unique": False}
    ]


def test_ensure_index_skips_drop_when_spec_already_matches():
    database = MongoDatabase(Settings(_env_file=None))
    collection = _StaleIndexCollection(stale_key=[("localidad", 1)])

    asyncio.run(database._ensure_index(
        collection,
        [("localidad", 1)],
        name="asociacion_localidad_orden",
    ))

    assert collection.dropped == []
    assert collection.created == [
        {"keys": [("localidad", 1)], "name": "asociacion_localidad_orden", "unique": False}
    ]
