import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
APP = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
HTML = (FRONTEND / "index.html").read_text(encoding="utf-8")
STATE_PATH = FRONTEND / "js" / "estado-carteles.js"


def _evaluate_states() -> list[dict]:
    script = f"""
import {{estadoCartel, formatearFechaMedicion}} from {json.dumps(STATE_PATH.as_uri())};
const card={{source:"zentra",unit:"°C"}};
const inputs=[
  {{estado:"cargando"}},
  {{estado:"ok",valor:21.4,unidad:"°C",datetime_local:"2026-09-05T11:30:00-04:00",fuente:"zentra"}},
  {{estado:"sin_datos",valor:null}},
  {{estado:"sin_asociacion",valor:null}},
  {{estado:"no_disponible",valor:null}},
  {{estado:"ok",valor:"no-numérico",unidad:"°C"}},
  {{estado:"ok",valor:8.5,unidad:null}},
  null,
];
console.log(JSON.stringify({{
  states:inputs.map(item=>estadoCartel(item,card)),
  invalidDate:formatearFechaMedicion("2026-99-99"),
  localDate:formatearFechaMedicion("2026-09-02"),
}}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_card_state_model_distinguishes_loading_data_absence_and_connection_error():
    result = _evaluate_states()
    states = result["states"]
    assert [item["status"] for item in states] == [
        "loading", "available", "no_data", "no_data", "error", "error", "available", "no_data"
    ]
    assert [item["text"] for item in states] == [
        "Cargando…", "21,4 °C", "Sin datos", "Sin datos", "Sin conexión", "Sin conexión", "8,5", "Sin datos"
    ]
    assert states[1]["value"] == 21.4
    assert states[1]["unit"] == "°C"
    assert states[1]["datetime"] == "2026-09-05T11:30:00-04:00"
    assert states[1]["is_stale"] is None
    assert states[1]["updatedText"].startswith("Actualizado: 5 sept 2026")
    assert result["invalidDate"] == ""
    assert result["localDate"].startswith("2 sept 2026")


def test_cards_render_server_values_as_text_and_keep_one_polite_live_region():
    assert 'valor.textContent=estado.text' in APP
    assert "innerHTML=estado" not in APP
    assert 'id="educational-detail-status"' in HTML
    assert 'role="status"' in HTML
    assert 'aria-live="polite"' in HTML
    assert HTML.count('aria-live="polite"') == 1
    assert 'anunciarCarteles("Cargando datos de "+nombreLocalidad)' in APP
    assert '"Datos de "+nombreLocalidad+" actualizados"' in APP
    assert '"No fue posible conectar con el servidor"' in APP


def test_school_changes_clear_cards_and_ignore_out_of_order_responses():
    load_start = APP.index("async function cargar()")
    loading_assignment = APP.index("dashboard=estadoInicial()", load_start)
    request = APP.index("fetchUltimasEducativas(localidadSolicitada)", load_start)
    assert loading_assignment < request
    assert "const ciclo=++cicloCarga,localidadSolicitada=localidad" in APP
    assert "ciclo!==cicloCarga||localidadSolicitada!==localidad" in APP
    assert "function seleccionarLocalidad(clave)" in APP
    assert "actualizar();cargar()" in APP


def test_partial_responses_and_manual_rulers_are_updated_without_fake_scales():
    assert "new Map((Array.isArray(items)?items:[])" in APP
    assert "estadoCartel(lecturas.get(item.key),item)" in APP
    assert 'regla.dataset.measurementValue=String(estado.value)' in APP
    assert 'regla.dataset.measurementUnit=estado.unit' in APP
    assert 'regla.dataset.measurementDatetime=estado.datetime||""' in APP
    assert "is_stale: null" in STATE_PATH.read_text(encoding="utf-8")


def test_existing_refresh_graph_history_and_keyboard_paths_remain_present():
    for token in (
        'document.querySelectorAll(".refresh").forEach(button=>button.onclick=cargar)',
        "fetchHistorialEducativo(localidad,clave",
        "crearGraficos()",
        'evento.key==="Escape"',
        'cartel.setAttribute("aria-label"',
    ):
        assert token in APP
