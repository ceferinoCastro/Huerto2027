"""Campaign repair: real persistence methods against an isolated collection double."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.mongodb import MongoDatabase
from app.main import create_app


def matches(doc, query):
    for key, value in query.items():
        if key == "$or":
            if not any(matches(doc, part) for part in value):
                return False
        elif isinstance(value, dict):
            if "$in" in value and doc.get(key) not in value["$in"]:
                return False
            if "$exists" in value and (key in doc) != value["$exists"]:
                return False
        elif doc.get(key) != value:
            return False
    return True


class CampaignCollection:
    def __init__(self):
        # Deliberately historical: no revision, audit or new closing fields.
        self.documents = [{"_id": "camp_dev_huayquique", "colegio_id": "huayquique-test",
            "nombre": "PRUEBA Huayquique", "especie": "lechuga", "desde": "2026-09-01",
            "hasta": "2026-12-01", "estado": "activa", "descripcion": "Observación original",
            "mediciones_ids": ["medicion-intacta"]}]
        self.writes = []
        self.force_conflict = False

    async def find_one(self, query):
        return next((deepcopy(d) for d in self.documents if matches(d, query)), None)

    def find(self, query):
        async def to_list(length):
            return [deepcopy(d) for d in self.documents if matches(d, query)][:length]
        return SimpleNamespace(to_list=to_list)

    async def update_one(self, query, update):
        self.writes.append((deepcopy(query), deepcopy(update)))
        for doc in self.documents:
            if matches(doc, query) and not self.force_conflict:
                assert set(update) == {"$set"}
                doc.update(deepcopy(update["$set"]))
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def create_index(self, *args, **kwargs):
        return None

    async def insert_one(self, document):
        self.documents.append(deepcopy(document))


class CampaignDatabase(MongoDatabase):
    def __init__(self):
        super().__init__(Settings(_env_file=None))
        self.collection = CampaignCollection()
        # Any accidental access to measurement collections fails immediately.
        self._database = {"campania": self.collection}
        self.measurements = {"lecturas": [{"valor": 12}], "mediciones_hanna": [{"ph": 7}],
                             "mediciones_plantas": [{"altura_cm": 15}]}

    async def connect(self): pass
    def close(self): pass

    async def college_by_id(self, college_id):
        assert college_id == "huayquique-test"
        return {"_id": college_id, "nombre": "Huayquique PRUEBA", "comuna": "Huayquique"}


def safe_app():
    db = CampaignDatabase()
    return create_app(Settings(_env_file=None), db), db


def finish_payload(**overrides):
    return {"fecha_cosecha_real": "2026-10-01", "resultado_final": "Cosecha de prueba",
            "observaciones_finales": "", "confirmar": True, "revision": 0, **overrides}


BASE = "/api/v1/campanias/camp_dev_huayquique"


def test_old_finish_payload_reproduces_exact_missing_fields():
    app, db = safe_app()
    with TestClient(app) as client:
        response = client.put(BASE + "/finalizar", json={"fecha_cosecha_real": "2026-10-01"})
    assert response.status_code == 422
    assert [e["loc"] for e in response.json()["detail"]] == [
        ["body", "resultado_final"], ["body", "confirmar"]]
    assert not db.collection.writes


def test_edit_then_finish_legacy_campaign_preserves_measurements_and_audits():
    app, db = safe_app()
    before = deepcopy(db.measurements)
    with TestClient(app) as client:
        edit = client.patch(BASE, json={"nombre": "PRUEBA editada", "cultivo": "tomate",
            "fecha_siembra": "2026-09-02", "fecha_cosecha_estimada": "2026-12-02",
            "observaciones": "  Observación revisada  ", "revision": 0})
        assert edit.status_code == 200, edit.text
        assert edit.json()["estado"] == "activa"
        assert edit.json()["revision"] == 1
        assert edit.json()["observaciones"] == "Observación revisada"
        assert db.collection.documents[0]["especie"] == "tomate"
        assert db.collection.documents[0]["desde"] == "2026-09-02"
        conflict = client.patch(BASE, json={"observaciones": "Otra edición", "revision": 0})
        assert conflict.status_code == 409
        finished = client.put(BASE + "/finalizar", json=finish_payload(revision=1))
        assert finished.status_code == 200, finished.text
        assert finished.json()["estado"] == "finalizada"
        assert finished.json()["resultado_final"] == "Cosecha de prueba"
        assert finished.json()["revision"] == 2
        assert len(finished.json()["historial_cambios"]) == 2
        assert client.get("/api/v1/campanias/activa?colegio_id=huayquique-test").json()["item"] is None
        history = client.get("/api/v1/campanias?colegio_id=huayquique-test").json()
        assert history["count"] == 1
        assert history["items"][0]["estado"] == "finalizada"
        assert client.put(BASE + "/finalizar", json=finish_payload(revision=2)).status_code == 409
    assert db.measurements == before
    assert db.collection.documents[0]["mediciones_ids"] == ["medicion-intacta"]


@pytest.mark.parametrize("change,status", [
    ({"fecha_cosecha_real": "2026-08-31"}, 409),
    ({"resultado_final": "   "}, 422), ({"resultado_final": ""}, 422),
    ({"confirmar": False}, 422), ({"fecha_cosecha_real": ""}, 422),
])
def test_invalid_finish_does_not_write(change, status):
    app, db = safe_app()
    with TestClient(app) as client:
        assert client.put(BASE + "/finalizar", json=finish_payload(**change)).status_code == status
    assert not db.collection.writes


@pytest.mark.parametrize("payload,status", [
    ({"colegio_id": "otro"}, 422), ({"estado": "finalizada"}, 422),
    ({"cultivo": "   "}, 409), ({"fecha_cosecha_estimada": "2026-08-01"}, 409),
    ({"resultado_final": "No editable"}, 409),
])
def test_edit_rejects_protected_fields_and_invalid_values(payload, status):
    app, db = safe_app()
    with TestClient(app) as client:
        assert client.patch(BASE, json=payload).status_code == status
    assert not db.collection.writes


def test_edit_can_set_and_clear_variable_thresholds():
    app, db = safe_app()
    with TestClient(app) as client:
        set_ranges = client.patch(BASE, json={
            "revision": 0,
            "rangos_variables": {
                "temperatura_aire": {"min": 10.0, "max": 35.0},
                "humedad_tierra": {"min": None, "max": 60.0},
            },
        })
        assert set_ranges.status_code == 200, set_ranges.text
        assert set_ranges.json()["rangos_variables"] == {
            "temperatura_aire": {"min": 10.0, "max": 35.0},
            "humedad_tierra": {"min": None, "max": 60.0},
        }
        clear_ranges = client.patch(BASE, json={"revision": 1, "rangos_variables": {}})
        assert clear_ranges.status_code == 200, clear_ranges.text
        assert clear_ranges.json()["rangos_variables"] == {}


def test_variable_threshold_rejects_max_below_min():
    app, db = safe_app()
    with TestClient(app) as client:
        response = client.patch(BASE, json={
            "revision": 0,
            "rangos_variables": {"temperatura_aire": {"min": 30.0, "max": 10.0}},
        })
    assert response.status_code == 422
    assert not db.collection.writes


def test_legacy_campaign_without_variable_thresholds_returns_empty_dict():
    app, db = safe_app()
    assert "rangos_variables" not in db.collection.documents[0]
    with TestClient(app) as client:
        response = client.get("/api/v1/campanias?colegio_id=huayquique-test")
    assert response.json()["items"][0]["rangos_variables"] == {}


def test_create_campaign_persists_variable_thresholds():
    app, db = safe_app()
    with TestClient(app) as client:
        db.collection.documents.clear()
        response = client.post("/api/v1/campanias", json={
            "colegio_id": "huayquique-test", "cultivo": "lechuga",
            "fecha_siembra": "2026-09-01", "fecha_cosecha_estimada": "2026-12-01",
            "rangos_variables": {"ph_agua": {"min": 6.0, "max": 7.5}},
        })
    assert response.status_code == 201, response.text
    assert response.json()["rangos_variables"] == {"ph_agua": {"min": 6.0, "max": 7.5}}


def test_atomic_conflict_does_not_overwrite_campaign():
    app, db = safe_app()
    original = deepcopy(db.collection.documents)
    db.collection.force_conflict = True
    with TestClient(app) as client:
        assert client.patch(BASE, json={"observaciones": "Cambio"}).status_code == 409
    assert db.collection.documents == original


def test_legacy_object_id_and_missing_dates_can_be_edited_without_inventing_data():
    from bson import ObjectId
    app, db = safe_app()
    identifier = ObjectId()
    item = db.collection.documents[0]
    item["_id"] = identifier
    del item["desde"]
    del item["hasta"]
    with TestClient(app) as client:
        edit = client.patch(f"/api/v1/campanias/{identifier}", json={"observaciones": ""})
        assert edit.status_code == 200
        assert edit.json()["fecha_siembra"] is None
        assert edit.json()["observaciones"] == ""
        finish = client.put(f"/api/v1/campanias/{identifier}/finalizar", json=finish_payload(revision=1))
        assert finish.status_code == 200
        assert finish.json()["fecha_siembra"] is None
        assert finish.json()["estado"] == "finalizada"
