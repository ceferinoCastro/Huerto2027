from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.domain import DomainConflictError, DomainNotFoundError


class CartelDatabase:
    def __init__(self):
        self.items = {}
        self.asociaciones_activas = set()

    async def connect(self):
        pass

    def close(self):
        pass

    async def list_carteles(self, force_refresh=False):
        return list(self.items.values())

    async def create_cartel(self, data):
        self.items[data["clave_educativa"]] = {"_id": data["clave_educativa"], **data}
        return self.items[data["clave_educativa"]]

    async def update_cartel(self, clave, data):
        if clave not in self.items:
            raise DomainNotFoundError("Cartel no encontrado")
        self.items[clave].update(data)
        return self.items[clave]

    async def delete_cartel(self, clave):
        if clave in self.asociaciones_activas:
            raise DomainConflictError("No se puede eliminar un cartel con asociaciones activas")
        if clave not in self.items:
            raise DomainNotFoundError("Cartel no encontrado")
        del self.items[clave]


def payload(**overrides):
    base = {
        "clave_educativa": "temperatura_aire",
        "nombre_educativo": "Temperatura del aire",
        "unidad": "°C",
        "categoria": "temperatura",
        "orden": 1,
        "visible_frontend": True,
    }
    return {**base, **overrides}


def test_cartel_crud_contract_used_by_frontend2():
    database = CartelDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        created = client.post("/api/v1/carteles", json=payload())
        listed = client.get("/api/v1/carteles")
        updated = client.put("/api/v1/carteles/temperatura_aire", json=payload(orden=2))
        deleted = client.delete("/api/v1/carteles/temperatura_aire")
    assert created.status_code == 201
    assert listed.json()["count"] == 1
    assert updated.json()["orden"] == 2
    assert deleted.json() == {"status": "ok", "deleted": True}


def test_update_rejects_mismatched_clave_between_body_and_route():
    database = CartelDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        client.post("/api/v1/carteles", json=payload())
        response = client.put("/api/v1/carteles/otra_clave", json=payload())
    assert response.status_code == 422


def test_delete_blocks_when_cartel_has_active_associations():
    database = CartelDatabase()
    database.asociaciones_activas.add("temperatura_aire")
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        client.post("/api/v1/carteles", json=payload())
        response = client.delete("/api/v1/carteles/temperatura_aire")
    assert response.status_code == 409


def test_delete_missing_cartel_returns_404():
    database = CartelDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.delete("/api/v1/carteles/no_existe")
    assert response.status_code == 404


def test_create_rejects_invalid_key_format():
    database = CartelDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.post("/api/v1/carteles", json=payload(clave_educativa="Con Espacios"))
    assert response.status_code == 422


def test_editing_a_cartel_preserves_technical_hint_fields_when_client_resends_them():
    # Regresión: frontend2 perdía fuente_sugerida/variable_tecnica_sugerida/
    # sensor_modelo_sugerido al editar un cartel porque el payload de "guardar
    # cartel" no los reenviaba en el PUT (reemplazo completo, no merge). El
    # fix vive en frontend2/app.js (payloadFormularioCartel ahora conserva los
    # valores originales); este test protege el contrato: si el cliente
    # reenvía esos tres campos tal cual, deben sobrevivir intactos.
    database = CartelDatabase()
    app = create_app(Settings(_env_file=None), database)
    original = payload(
        fuente_sugerida="zentra",
        variable_tecnica_sugerida="Air Temperature",
        sensor_modelo_sugerido="ATMOS 14",
    )
    with TestClient(app) as client:
        client.post("/api/v1/carteles", json=original)
        updated = client.put(
            "/api/v1/carteles/temperatura_aire",
            json={**original, "nombre_educativo": "Temperatura Atmosférica"},
        )
    assert updated.status_code == 200
    body = updated.json()
    assert body["nombre_educativo"] == "Temperatura Atmosférica"
    assert body["fuente_sugerida"] == "zentra"
    assert body["variable_tecnica_sugerida"] == "Air Temperature"
    assert body["sensor_modelo_sugerido"] == "ATMOS 14"
