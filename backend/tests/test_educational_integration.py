from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.sensor_associations import EDUCATIONAL_VARIABLES


ROOT = Path(__file__).resolve().parents[2]


def association(locality, variable, source="zentra", **extra):
    return {
        "colegio_id": f"college-{locality}",
        "localidad": locality,
        "clave_educativa": variable,
        "nombre_educativo": variable.replace("_", " ").title(),
        "source": source,
        "device_sn": extra.get("device_sn", "device-1"),
        "sensor_sn": extra.get("sensor_sn", "sensor-1"),
        "variable_tecnica": extra.get("variable_tecnica", "Technical Variable"),
        "unidad": extra.get("unidad", "°C"),
        "estado_asociacion": extra.get("estado_asociacion", "asociada"),
        "visible_frontend": extra.get("visible_frontend", True),
    }


class EducationalDatabase:
    def __init__(self):
        self.associations = {
            ("pica", "temperatura_aire"): association(
                "pica",
                "temperatura_aire",
                device_sn="z6-29235",
                sensor_sn="A14G200012094",
                variable_tecnica="Air Temperature",
            ),
            ("pica", "temperatura_agua"): association(
                "pica", "temperatura_agua", "hanna", sensor_sn="HANNA-1"
            ),
            ("pica", "altura_planta"): association(
                "pica", "altura_planta", "manual", variable_tecnica="altura_cm", unidad="cm"
            ),
            ("huara", "temperatura_aire"): association(
                "huara", "temperatura_aire", sensor_sn="ATMOS-HUARA"
            ),
        }
        self.latest = {
            ("pica", "temperatura_aire"): {"value": 23.8, "units": "°C", "datetime": "2026-08-04T10:30:00-04:00", "timestamp_utc": 1785853800},
            ("pica", "temperatura_agua"): {"value": 24.5, "units": "°C", "datetime": "2026-08-06T14:30:00", "timestamp_utc": 1786041000},
            ("pica", "altura_planta"): {"value": 31.2, "units": "cm", "datetime": "2026-09-02", "timestamp_utc": 1788307200},
            ("huara", "temperatura_aire"): {"value": 19.4, "units": "°C", "datetime": "2026-08-04T10:30:00-04:00", "timestamp_utc": 1785853800},
        }
        self.hanna_equipment = {
            "college-pica": {"serial_hanna": "HANNA-1", "modelo": "HI981420", "instrument_id": "0003"}
        }
        self.hanna_documents = {
            ("college-pica", "temp_avg_c"): {
                "temp_avg_c": 24.5,
                "datetime_local": "2026-08-06T14:30:00",
                "fecha": "2026-08-06",
                "hora": "14:30:00",
            }
        }
        self.campaign_calls = []
        self.series_calls = []

    async def connect(self): pass
    def close(self): pass
    async def college_by_locality(self, locality):
        return {"_id": f"college-{locality}", "nombre": locality.title()}
    async def sensor_association(self, locality, variable):
        return self.associations.get((locality, variable))
    async def list_sensor_associations(self, locality):
        return [item for (item_locality, _variable), item in self.associations.items() if item_locality == locality]
    async def hanna_scope_for_locality(self, locality):
        assigned = [
            item["sensor_sn"]
            for (item_locality, _variable), item in self.associations.items()
            if item_locality == locality and item["source"] == "hanna" and item.get("sensor_sn")
        ]
        return assigned, assigned
    async def latest_hanna_field_for_college(self, college_id, field):
        equipment = self.hanna_equipment.get(college_id)
        if equipment is None:
            return {"estado": "sin_equipo_hanna", "documento": None}
        metadata = {**equipment}
        document = self.hanna_documents.get((college_id, field))
        if document is None:
            return {"estado": "sin_datos_validos", "documento": None, **metadata}
        return {"estado": "ok", "documento": document, **metadata}
    async def latest_associated_measurement(self, item):
        return self.latest.get((item["localidad"], item["clave_educativa"]))
    async def associated_measurement_series(self, item, since, until):
        self.series_calls.append((item["localidad"], item["clave_educativa"], since, until))
        latest = await self.latest_associated_measurement(item)
        return [latest] if latest and since <= latest["timestamp_utc"] <= until else []
    async def campaign_period(self, campaign_id, college_id):
        self.campaign_calls.append((campaign_id, college_id))
        return {"desde": "2026-08-01", "hasta": "2026-08-31"}


def test_latest_summary_dispatches_zentra_hanna_manual_and_missing_association():
    database = EducationalDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.get("/api/v1/localidades/pica/variables-educativas/ultima")
    items = {item["variable"]: item for item in response.json()["items"]}
    assert response.status_code == 200
    assert items["temperatura_aire"]["valor"] == 23.8
    assert items["temperatura_aire"]["fuente"] == "zentra"
    assert items["temperatura_agua"]["fuente"] == "hanna"
    assert items["altura_planta"]["fuente"] == "manual"
    assert items["humedad_aire"]["estado"] == "sin_asociacion"
    detail = items["temperatura_aire"]["detalle_tecnico"]
    assert detail == {
        "clave_educativa": "temperatura_aire",
        "colegio_id": "college-pica",
        "fuente": "zentra",
        "coleccion": "lecturas",
        "device_sn": "z6-29235",
        "sensor_sn": "A14G200012094",
        "sensor_modelo": "ATMOS 14",
        "variable_tecnica": "Air Temperature",
        "campo_consultado": "value",
        "unidad_original": "°C",
        "fecha_original": "2026-08-04T10:30:00-04:00",
        "estado_asociacion": "asociada",
        "serial_hanna": None,
        "modelo": None,
        "instrument_id": None,
        "estado": "ok",
    }


def test_hanna_cards_resolve_from_college_equipment_without_sensor_association():
    database = EducationalDatabase()
    database.associations.pop(("pica", "temperatura_agua"))
    database.hanna_documents.update({
        ("college-pica", "ph_avg"): {"ph_avg": 7.19, "datetime_local": "2026-08-01T08:25:36"},
        ("college-pica", "ec_avg_ms_cm"): {"ec_avg_ms_cm": 0.65, "datetime_local": "2026-08-01T08:25:36"},
    })
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.get("/api/v1/localidades/pica/variables-educativas/ultima")

    items = {item["variable"]: item for item in response.json()["items"]}
    assert items["ph_agua"]["valor"] == 7.19
    assert items["sales_agua"]["valor"] == 0.65
    assert items["temperatura_agua"]["valor"] == 24.5
    assert all(items[key]["fuente"] == "hanna" for key in ("ph_agua", "sales_agua", "temperatura_agua"))
    assert items["temperatura_agua"]["detalle_tecnico"]["serial_hanna"] == "HANNA-1"
    assert items["temperatura_agua"]["detalle_tecnico"]["coleccion"] == "mediciones_hanna"
    assert items["temperatura_agua"]["detalle_tecnico"]["campo_consultado"] == "temp_avg_c"


def test_associated_sensor_without_readings_returns_sin_datos():
    database = EducationalDatabase()
    database.associations[("pica", "humedad_tierra")] = association(
        "pica", "humedad_tierra", variable_tecnica="Water Content", unidad="m³/m³"
    )
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.get("/api/v1/localidades/pica/variables-educativas/humedad_tierra/ultima")
    assert response.json()["estado"] == "sin_datos"
    assert response.json()["valor"] is None
    assert response.json()["mensaje"] == "Sensor asociado, pero sin mediciones"
    assert response.json()["detalle_tecnico"]["coleccion"] == "lecturas"


def test_hanna_without_equipment_and_manual_without_records_are_distinct():
    database = EducationalDatabase()
    database.hanna_equipment.pop("college-pica")
    database.associations[("pica", "largo_raiz")] = association(
        "pica", "largo_raiz", "manual", variable_tecnica="largo_raiz_cm", unidad="cm"
    )
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        hanna = client.get("/api/v1/localidades/pica/variables-educativas/temperatura_agua/ultima")
        manual = client.get("/api/v1/localidades/pica/variables-educativas/largo_raiz/ultima")

    assert hanna.json()["estado"] == "sin_equipo_hanna"
    assert hanna.json()["mensaje"] == "Este huerto no tiene un equipo Hanna asociado"
    assert hanna.json()["detalle_tecnico"]["coleccion"] == "mediciones_hanna"
    assert manual.json()["estado"] == "sin_datos"
    assert manual.json()["mensaje"] == "Aún no hay mediciones de planta"
    assert manual.json()["detalle_tecnico"]["coleccion"] == "mediciones_plantas"


def test_latest_summary_includes_additional_active_educational_variables():
    database = EducationalDatabase()
    database.associations[("pica", "radiacion_solar")] = association(
        "pica", "radiacion_solar", variable_tecnica="Solar Radiation", unidad="W/m²"
    )
    database.latest[("pica", "radiacion_solar")] = {
        "value": 640.0,
        "units": "W/m²",
        "datetime": "2026-09-03T14:30:00-04:00",
        "timestamp_utc": 1788460200,
    }
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.get("/api/v1/localidades/pica/variables-educativas/ultima")

    items = {item["variable"]: item for item in response.json()["items"]}
    assert items["radiacion_solar"]["valor"] == 640.0
    assert items["radiacion_solar"]["detalle_tecnico"]["sensor_modelo"] is None
    assert response.json()["count"] == len(EDUCATIONAL_VARIABLES) + 1


def test_latest_summary_exposes_the_single_ordered_poster_catalog():
    database = EducationalDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.get("/api/v1/localidades/pica/variables-educativas/ultima")

    catalog = response.json()["catalogo"]
    assert len(catalog) == 11
    assert [item["orden"] for item in catalog] == list(range(1, 12))
    assert [item["clave_educativa"] for item in catalog] == [
        definition[0] for definition in EDUCATIONAL_VARIABLES
    ]
    assert [item["fuente"] for item in catalog] == [
        "zentra", "zentra", "zentra", "zentra", "zentra", "zentra",
        "hanna", "hanna", "hanna", "manual", "manual",
    ]
    assert catalog[6]["variable_tecnica"] == "ph_avg"
    assert catalog[7]["variable_tecnica"] == "ec_avg_ms_cm"
    assert catalog[8]["variable_tecnica"] == "temp_avg_c"
    assert catalog[9]["variable_tecnica"] == "altura_cm"
    assert catalog[10]["variable_tecnica"] == "largo_raiz_cm"


def test_latest_summary_returns_diagnostic_cards_when_backend_fails():
    database = EducationalDatabase()

    async def fail(_locality):
        raise RuntimeError("database unavailable")

    database.list_sensor_associations = fail
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.get("/api/v1/localidades/pica/variables-educativas/ultima")

    assert response.status_code == 503
    assert len(response.json()["catalogo"]) == len(EDUCATIONAL_VARIABLES)
    assert len(response.json()["items"]) == len(EDUCATIONAL_VARIABLES)
    assert all(item["estado"] == "no_disponible" for item in response.json()["items"])
    assert response.json()["items"][0]["mensaje"] == "No fue posible consultar esta medición"


def test_general_history_does_not_consult_campaign_and_explicit_campaign_does():
    database = EducationalDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        general = client.get(
            "/api/v1/localidades/pica/variables-educativas/temperatura_aire/historial",
            params={"desde": "2026-08-01", "hasta": "2026-08-31"},
        )
        assert database.campaign_calls == []
        campaign = client.get(
            "/api/v1/localidades/pica/variables-educativas/temperatura_aire/historial",
            params={"campania_id": "camp_1"},
        )
    assert general.json()["estado"] == "ok"
    assert campaign.json()["periodo"]["campania_id"] == "camp_1"
    assert database.campaign_calls == [("camp_1", "college-pica")]


def test_default_history_is_anchored_to_latest_real_measurement():
    database = EducationalDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/localidades/pica/variables-educativas/temperatura_aire/historial",
            params={"horas": 24},
        )
    assert response.json()["estado"] == "ok"
    assert response.json()["items"][-1]["value"] == 23.8


def test_college_change_and_association_change_are_not_cached():
    database = EducationalDatabase()
    app = create_app(Settings(_env_file=None), database)
    with TestClient(app) as client:
        pica = client.get("/api/v1/localidades/pica/variables-educativas/temperatura_aire/ultima")
        huara = client.get("/api/v1/localidades/huara/variables-educativas/temperatura_aire/ultima")
        missing = client.get("/api/v1/localidades/pica/variables-educativas/humedad_aire/ultima")
        database.associations[("pica", "humedad_aire")] = association("pica", "humedad_aire")
        database.latest[("pica", "humedad_aire")] = {"value": 61.0, "units": "%", "datetime": "2026-09-03", "timestamp_utc": 1788393600}
        refreshed = client.get("/api/v1/localidades/pica/variables-educativas/humedad_aire/ultima")
    assert pica.json()["valor"] == 23.8
    assert huara.json()["valor"] == 19.4
    assert missing.json()["estado"] == "sin_asociacion"
    assert refreshed.json()["valor"] == 61.0


def test_frontend_uses_educational_keys_without_demo_or_local_storage_fallback():
    app_js = (ROOT / "frontend/js/app.js").read_text()
    api_js = (ROOT / "frontend/js/api.js").read_text()
    assert '"temperatura_aire","temperatura_tierra","temperatura_bajo_tierra","temperatura_agua"' in app_js
    assert "humedad_hojas" in app_js
    assert "puntosDemo" not in app_js
    assert "sensores[clave].datos" not in app_js
    assert "Dato demostrativo" not in app_js
    assert "localStorage" not in api_js
    assert "fetchHistorialEducativo(localidad,clave" in app_js
    assert 'faltantes.join(", ")' in app_js
