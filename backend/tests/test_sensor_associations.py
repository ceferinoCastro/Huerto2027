from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.domain import DomainNotFoundError
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
    assert by_key(proposal, "humedad_aire")["estado_asociacion"] == "pendiente"
    assert by_key(proposal, "humedad_hojas")["estado_asociacion"] == "pendiente"
    assert by_key(proposal, "temperatura_tierra")["confianza"] == "alta"
    assert by_key(proposal, "temperatura_bajo_tierra")["confianza"] == "alta"


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
        "nombre_educativo": "Temperatura del aire",
        "sensor_sn": "ATMOS-1",
        "variable_tecnica": "Air Temperature",
        "unidad": "°C",
        "categoria": "temperatura",
        "orden": 1,
    }
    with TestClient(app) as client:
        created = client.post("/api/v1/asociaciones-sensores", json=payload)
        listed = client.get("/api/v1/asociaciones-sensores", params={"localidad": "pica"})
        updated = client.put("/api/v1/asociaciones-sensores/64f000000000000000000001", json={**payload, "orden": 2})
        deleted = client.delete("/api/v1/asociaciones-sensores/64f000000000000000000001")
    assert created.status_code == 201
    assert listed.json()["count"] == 1
    assert updated.json()["orden"] == 2
    assert deleted.json() == {"status": "ok", "deleted": True}
