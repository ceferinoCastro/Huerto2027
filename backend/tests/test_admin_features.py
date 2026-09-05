from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.compatibility import campaign_to_public
from app.services.domain import DomainConflictError, DomainNotFoundError
from app.services.hanna_csv import decode_hanna_file, parse_hanna_csv, parse_hanna_metadata


def hanna_csv(serial: str, instrument: str = "0003", day: str = "07/07/2026") -> bytes:
    lines = [
        "Model;HI981420",
        f"Serial #;{serial}",
        f"Instrument ID;{instrument}",
        *[f"Metadata {index};value" for index in range(4, 22)],
        "Date;Time;Min;Unit;Max;Unit;Avg;Unit;Min;Unit;Max;Unit;Avg;Unit;Min;Unit;Max;Unit;Avg;Unit;",
        f"{day};14:30:00;6,4;pH;6,8;pH;6,6;pH;1,0;mS/cm;1,2;mS/cm;1,1;mS/cm;21,0;°C;25,0;°C;24,5;°C;",
    ]
    return ("\n".join(lines) + "\n").encode("utf-16")


class InMemoryAdminDatabase:
    def __init__(self) -> None:
        self.colleges = {
            "pica-id": {"_id": "pica-id", "nombre": "Colegio Pica", "comuna": "Pica"},
            "huara-id": {"_id": "huara-id", "nombre": "Liceo de Huara", "comuna": "Huara"},
            "colchane-id": {"_id": "colchane-id", "nombre": "Liceo Colchane", "comuna": "Colchane"},
        }
        self.equipment: dict[str, dict] = {}
        self.measurements: dict[tuple[str, str], dict] = {}
        self.campaigns: dict[str, dict] = {}

    async def connect(self): pass
    def close(self): pass

    async def college_by_id(self, college_id):
        if college_id not in self.colleges:
            raise DomainNotFoundError("Colegio no encontrado")
        return self.colleges[college_id]

    async def college_by_locality(self, locality):
        return next((item for item in self.colleges.values() if item["comuna"].lower() == locality), None)

    async def hanna_datalogger(self, serial):
        return self.equipment.get(serial.upper())

    async def list_hanna_dataloggers(self):
        return list(self.equipment.values())

    async def associate_hanna_datalogger(self, data):
        serial = data["serial_hanna"].upper()
        if serial in self.equipment:
            raise DomainConflictError("El serial Hanna ya está registrado")
        college = await self.college_by_id(data["colegio_id"])
        if any(item["colegio_id"] == data["colegio_id"] and item["estado"] == "activo" for item in self.equipment.values()):
            raise DomainConflictError("El colegio ya tiene un equipo Hanna activo")
        now = datetime.now(timezone.utc)
        item = {**data, "serial_hanna": serial, "colegio_nombre": college["nombre"], "localidad": college["comuna"].lower(), "estado": "activo", "fecha_asignacion": str(data["fecha_asignacion"]), "fecha_baja": None, "reemplazado_por": None, "created_at": now, "updated_at": now}
        self.equipment[serial] = item
        return item

    async def correct_hanna_assignment(self, serial, college_id, user):
        item = self.equipment.get(serial.upper())
        if not item:
            raise DomainNotFoundError("Equipo Hanna no encontrado")
        if any(other["colegio_id"] == college_id and other["estado"] == "activo" and other["serial_hanna"] != serial.upper() for other in self.equipment.values()):
            raise DomainConflictError("El colegio de destino ya tiene un Hanna activo")
        college = await self.college_by_id(college_id)
        item.update({"colegio_id": college_id, "colegio_nombre": college["nombre"], "localidad": college["comuna"].lower(), "updated_at": datetime.now(timezone.utc)})
        return item

    async def replace_hanna_datalogger(self, serial, data):
        old = self.equipment.get(serial.upper())
        if not old:
            raise DomainNotFoundError("Equipo Hanna no encontrado")
        if old["estado"] != "activo":
            raise DomainConflictError("Solo un equipo activo puede ser reemplazado")
        new_serial = data["serial_hanna_nuevo"].upper()
        if new_serial in self.equipment:
            raise DomainConflictError("El serial nuevo ya está registrado")
        old.update({"estado": "reemplazado", "fecha_baja": str(data["fecha_asignacion"]), "reemplazado_por": new_serial})
        new = await self.associate_hanna_datalogger({"serial_hanna": new_serial, "modelo": data["modelo"], "instrument_id": data["instrument_id"], "colegio_id": old["colegio_id"], "fecha_asignacion": data["fecha_asignacion"]})
        return {"anterior": old, "nuevo": new}

    async def hanna_scope_for_locality(self, locality):
        registered = list(self.equipment)
        assigned = [serial for serial, item in self.equipment.items() if item["localidad"] == locality]
        return assigned, registered

    async def upsert_hanna_measurements(self, documents):
        created = updated = 0
        for item in documents:
            key = (item["serial_hanna"], item["datetime_local"])
            if key in self.measurements: updated += 1
            else: created += 1
            self.measurements[key] = item
        return {"created": created, "updated": updated}

    def _scoped(self, locality, assigned, registered):
        return [item for item in self.measurements.values() if item["serial_hanna"] in assigned or (item["localidad"] == locality and item["serial_hanna"] not in registered)]

    async def latest_hanna_temperature(self, locality, assigned, registered):
        items = [item for item in self._scoped(locality, assigned, registered) if item["valido"] and item.get("temp_avg_c")]
        return max(items, key=lambda item: item["datetime_local"]) if items else None

    async def latest_hanna_field_for_college(self, college_id, field):
        equipment = [item for item in self.equipment.values() if item["colegio_id"] == college_id]
        if not equipment:
            return {"estado": "sin_equipo_hanna", "documento": None}
        serials = {item["serial_hanna"] for item in equipment}
        all_items = [item for item in self.measurements.values() if item["serial_hanna"] in serials]
        identity = equipment[0]
        metadata = {"serial_hanna": identity["serial_hanna"], "modelo": identity.get("modelo"), "instrument_id": identity.get("instrument_id")}
        if not all_items:
            return {"estado": "sin_datos", "documento": None, **metadata}
        valid = [item for item in all_items if item.get("valido") is True and item.get(field) is not None]
        if not valid:
            return {"estado": "sin_datos_validos", "documento": None, **metadata}
        document = max(valid, key=lambda item: item["datetime_local"])
        return {"estado": "ok", "documento": document, "serial_hanna": document["serial_hanna"], "modelo": identity.get("modelo"), "instrument_id": identity.get("instrument_id")}

    async def hanna_measurements_summary(self, locality, assigned, registered):
        items = self._scoped(locality, assigned, registered)
        return {"total_registros": len(items)} if items else None

    async def hanna_daily_temperature_series(self, locality, days, assigned, registered):
        items = [item for item in self._scoped(locality, assigned, registered) if item["valido"]]
        return [{"fecha": item["fecha"], "valor": item["temp_avg_c"]} for item in items[-days:]]

    async def campaigns_for_college(self, college_id):
        await self.college_by_id(college_id)
        return sorted([campaign_to_public(item, college_id) for item in self.campaigns.values() if item.get("colegio_id") == college_id or item.get("colegio") == self.colleges[college_id]["nombre"]], key=lambda item: item.get("fecha_siembra") or "", reverse=True)

    async def active_campaign(self, college_id):
        return next((item for item in await self.campaigns_for_college(college_id) if item["estado"] == "activa"), None)

    async def create_campaign(self, data):
        if await self.active_campaign(data["colegio_id"]):
            raise DomainConflictError("El colegio ya tiene una campaña activa")
        identifier = f"camp_{len(self.campaigns) + 1}"
        item = {"_id": identifier, **data, "nombre": f"{data['cultivo'].capitalize()} — Pica — {str(data['fecha_siembra'])[:4]}", "fecha_siembra": str(data["fecha_siembra"]), "fecha_cosecha_estimada": str(data["fecha_cosecha_estimada"]), "fecha_cosecha_real": None, "estado": "activa", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
        self.campaigns[identifier] = item
        return campaign_to_public(item)

    async def finish_campaign(self, identifier, data):
        harvest = data["fecha_cosecha_real"]
        item = self.campaigns[identifier]
        if harvest < str(item.get("fecha_siembra") or item.get("desde")):
            raise DomainConflictError("La cosecha real no puede ser anterior a la siembra")
        item.update({"estado": "finalizada", "fecha_cosecha_real": harvest})
        return campaign_to_public(item)

    async def cancel_campaign(self, identifier):
        self.campaigns[identifier]["estado"] = "cancelada"
        return campaign_to_public(self.campaigns[identifier])


def client_and_db():
    database = InMemoryAdminDatabase()
    app = create_app(Settings(_env_file=None), database)
    return TestClient(app), database


@pytest.mark.parametrize("serial", ["GA05440096", "GA06130059", "GA04460088"])
def test_detects_required_hanna_serials(serial):
    assert parse_hanna_metadata(hanna_csv(serial), "archivo.csv")["equipo_serial"] == serial


def test_hanna_parser_tolerates_nuls_cp1252_degree_and_comma_decimals():
    header = "Date;Time;Min;Unit;Max;Unit;Avg;Unit;Min;Unit;Max;Unit;Avg;Unit;Min;Unit;Max;Unit;Avg;Unit"
    row = "13/07/2026;16:36:51;6,1;pH;6,3;pH;6,2;pH;1,1;mS/cm;1,3;mS/cm;1,2;mS/cm;20,1;°C;20,3;°C;20,2;°C"
    content = ("Model;HI981420\nSerial #;GA06130059\nInstrument ID;0005\n" + header + "\n" + row + "\n").encode("cp1252")
    content = content.replace(b"\n", b"\x00\n")

    decoded = decode_hanna_file(content)
    parsed = parse_hanna_csv(content, "colchane.csv")

    assert "°C" in decoded
    assert "\x00" not in decoded
    assert parsed["equipo_serial"] == "GA06130059"
    assert parsed["mediciones"][0]["temp_avg_c"] == 20.2
    assert parsed["mediciones"][0]["valido"] is True


def test_huara_files_are_the_same_equipment():
    first = parse_hanna_metadata(hanna_csv("GA04460088", day="06/07/2026"), "huara-1.csv")
    second = parse_hanna_metadata(hanna_csv("GA04460088", day="11/05/2026"), "huara-2.csv")
    assert first["equipo_serial"] == second["equipo_serial"]


def test_preview_requests_college_then_recognizes_associated_serial():
    client, database = client_and_db()
    with client:
        unknown = client.post("/api/v1/mediciones-hanna/analizar-csv", files={"archivo": ("pica.csv", hanna_csv("GA05440096"), "text/csv")})
        client.post("/api/v1/dataloggers-hanna/asociar", json={"serial_hanna": "GA05440096", "modelo": "HI981420", "instrument_id": "0003", "colegio_id": "pica-id", "fecha_asignacion": "2026-09-03"})
        known = client.post("/api/v1/mediciones-hanna/analizar-csv", files={"archivo": ("pica.csv", hanna_csv("GA05440096"), "text/csv")})
    assert unknown.json()["asociado"] is False
    assert known.json()["asociado"] is True
    assert known.json()["equipo"]["localidad"] == "pica"


def test_duplicate_serial_and_two_active_equipment_are_rejected():
    client, _ = client_and_db()
    payload = {"serial_hanna": "GA05440096", "colegio_id": "pica-id"}
    with client:
        assert client.post("/api/v1/dataloggers-hanna/asociar", json=payload).status_code == 201
        assert client.post("/api/v1/dataloggers-hanna/asociar", json=payload).status_code == 409
        assert client.post("/api/v1/dataloggers-hanna/asociar", json={"serial_hanna": "OTHER", "colegio_id": "pica-id"}).status_code == 409


def test_correction_immediately_changes_measurement_locality():
    client, _ = client_and_db()
    with client:
        client.post("/api/v1/dataloggers-hanna/asociar", json={"serial_hanna": "GA05440096", "colegio_id": "pica-id"})
        client.post("/api/v1/mediciones-hanna/importar-csv", files={"archivo": ("pica.csv", hanna_csv("GA05440096"), "text/csv")})
        changed = client.put("/api/v1/dataloggers-hanna/GA05440096/corregir-asignacion", json={"colegio_id": "huara-id", "confirmar": True})
        old = client.get("/api/v1/mediciones-hanna/ultima", params={"localidad": "pica", "variable": "temperatura"})
        new = client.get("/api/v1/mediciones-hanna/ultima", params={"localidad": "huara", "variable": "temperatura"})
    assert changed.status_code == 200
    assert old.json()["valor"] is None
    assert new.json()["valor"] == 24.5


def test_replacement_keeps_old_measurements_and_prevents_second_active():
    client, database = client_and_db()
    with client:
        client.post("/api/v1/dataloggers-hanna/asociar", json={"serial_hanna": "OLD", "colegio_id": "pica-id"})
        client.post("/api/v1/mediciones-hanna/importar-csv", files={"archivo": ("old.csv", hanna_csv("OLD"), "text/csv")})
        replaced = client.post("/api/v1/dataloggers-hanna/OLD/reemplazar", json={"serial_hanna_nuevo": "NEW", "fecha_asignacion": "2026-09-03"})
        latest = client.get("/api/v1/mediciones-hanna/ultima", params={"localidad": "pica", "variable": "temperatura"})
    assert replaced.status_code == 200
    assert replaced.json()["anterior"]["estado"] == "reemplazado"
    assert replaced.json()["nuevo"]["estado"] == "activo"
    assert ("OLD", "2026-07-07T14:30:00") in database.measurements
    assert latest.json()["valor"] == 24.5


def test_import_is_idempotent_by_serial_and_datetime():
    client, _ = client_and_db()
    with client:
        client.post("/api/v1/dataloggers-hanna/asociar", json={"serial_hanna": "GA05440096", "colegio_id": "pica-id"})
        first = client.post("/api/v1/mediciones-hanna/importar-csv", files={"archivo": ("pica.csv", hanna_csv("GA05440096"), "text/csv")})
        second = client.post("/api/v1/mediciones-hanna/importar-csv", files={"archivo": ("pica.csv", hanna_csv("GA05440096"), "text/csv")})
    assert first.json()["insertados"] == 1
    assert second.json()["insertados"] == 0
    assert second.json()["actualizados"] == 1


def test_campaign_lifecycle_history_and_date_validation():
    client, _ = client_and_db()
    payload = {"colegio_id": "pica-id", "cultivo": "tomate", "fecha_siembra": "2026-09-15", "fecha_cosecha_estimada": "2027-01-15", "observaciones": "Curso 5°"}
    with client:
        invalid = client.post("/api/v1/campanias", json={**payload, "fecha_cosecha_estimada": "2026-09-14"})
        created = client.post("/api/v1/campanias", json=payload)
        duplicate = client.post("/api/v1/campanias", json=payload)
        active = client.get("/api/v1/campanias/activa", params={"colegio_id": "pica-id"})
        invalid_finish = client.put("/api/v1/campanias/camp_1/finalizar", json={"fecha_cosecha_real": "2026-09-14", "resultado_final": "Cierre de prueba", "confirmar": True})
        finished = client.put("/api/v1/campanias/camp_1/finalizar", json={"fecha_cosecha_real": "2027-01-10", "resultado_final": "Cierre de prueba", "confirmar": True})
        history = client.get("/api/v1/campanias", params={"colegio_id": "pica-id"})
    assert invalid.status_code == 422
    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert active.json()["item"]["estado"] == "activa"
    assert invalid_finish.status_code == 409
    assert finished.json()["estado"] == "finalizada"
    assert history.json()["items"][0]["fecha_cosecha_real"] == "2027-01-10"


def test_campaign_can_be_cancelled_with_explicit_confirmation():
    client, _ = client_and_db()
    with client:
        client.post("/api/v1/campanias", json={"colegio_id": "huara-id", "cultivo": "lechuga", "fecha_siembra": "2026-09-01", "fecha_cosecha_estimada": "2026-12-01"})
        refused = client.put("/api/v1/campanias/camp_1/cancelar", json={"confirmar": False})
        cancelled = client.put("/api/v1/campanias/camp_1/cancelar", json={"confirmar": True})
    assert refused.status_code == 422
    assert cancelled.json()["estado"] == "cancelada"


def test_historical_campaign_fields_remain_compatible():
    old = campaign_to_public({"_id": "camp_old", "nombre": "Otoño", "colegio": "Colegio Pica", "especie": "Lechuga", "desde": "2025-03-01", "hasta": "2025-06-30", "estado": "finalizada", "descripción": "Histórica"}, "pica-id")
    assert old["cultivo"] == "Lechuga"
    assert old["fecha_siembra"] == "2025-03-01"
    assert old["fecha_cosecha_estimada"] == "2025-06-30"
    assert old["observaciones"] == "Histórica"


@pytest.mark.parametrize("state", ["finalizada", "cancelada"])
def test_historical_closed_campaign_never_blocks_because_of_future_until(state):
    old = campaign_to_public(
        {
            "_id": f"camp_{state}",
            "estado": state,
            "desde": "2026-01-01",
            "hasta": "2035-12-31",
            "especie": "Tomate",
        },
        "pica-id",
    )
    assert old["estado"] == state
    assert old["estado"] != "activa"
