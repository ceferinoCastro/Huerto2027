from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
HTML = (FRONTEND / "index.html").read_text(encoding="utf-8")
CSS = (FRONTEND / "css" / "estilos.css").read_text(encoding="utf-8")
APP = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
CATALOG_PATH = FRONTEND / "js" / "catalogo-carteles.js"


EXPECTED_EXPLANATIONS = {
    "temperatura_aire": "Indica qué tan cálido o frío está el aire alrededor de las plantas.",
    "humedad_aire": "Muestra cuánta humedad contiene el aire que rodea el huerto.",
    "humedad_hojas": "Indica si las hojas se encuentran secas o tienen agua sobre su superficie.",
    "temperatura_tierra": "Muestra la temperatura de la superficie de la tierra del huerto.",
    "temperatura_bajo_tierra": "Muestra la temperatura en la zona profunda de la tierra, cerca de las raíces.",
    "humedad_tierra": "Indica cuánta agua hay disponible en la tierra para las raíces.",
    "ph_agua": "Indica si el agua es más ácida, neutra o alcalina.",
    "sales_agua": "Muestra la cantidad de sales presentes en el agua del estanque.",
    "temperatura_agua": "Indica qué tan fría o cálida está el agua almacenada en el estanque.",
    "altura_planta": "Muestra cuánto ha crecido la planta desde la superficie de la tierra.",
    "largo_raiz": "Muestra cuánto ha crecido la raíz principal bajo la tierra.",
}


def _catalog() -> list[dict]:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_frontend_stage2_visualization import BACKEND_ITEMS, _cargar_catalogo_visual

    return _cargar_catalogo_visual(BACKEND_ITEMS)


def test_there_is_one_detail_panel_immediately_after_the_scene():
    assert HTML.count('id="educational-detail-panel"') == 1
    assert re.search(
        r'</section>\s*<section id="educational-detail-panel"',
        HTML[HTML.index('<section class="huerto-scene"'):],
    )
    assert "position:absolute" not in CSS[
        CSS.index(".educational-detail{"):CSS.index(".educational-detail__primary{")
    ]


def test_initial_panel_invites_the_student_without_preselection():
    assert 'selectedEducationalVariableKey=null' in APP
    assert "Explora el huerto" in HTML
    assert "Selecciona un cartel para conocer esta medición." in HTML
    assert 'data-detail-state="empty"' in HTML


def test_catalog_contains_the_exact_educational_explanations():
    assert {item["key"]: item["explanation"] for item in _catalog()} == EXPECTED_EXPLANATIONS


def test_one_selection_state_drives_cards_markers_connections_and_panel():
    assert APP.count("let localidad=") == 1
    assert "sensorActivo" not in APP
    assert "function seleccionarVariableEducativa(clave" in APP
    assert "selectedEducationalVariableKey=clave" in APP
    assert 'elemento.classList.toggle("is-selected",esCartelSeleccionado)' in APP
    assert 'elemento.setAttribute("aria-pressed",String(' in APP
    assert "renderEducationalState()" in APP
    assert ".sensor-card.is-selected" in CSS


def test_detail_uses_the_loaded_measurement_and_never_fetches_on_selection():
    selection = APP[APP.index("function seleccionarVariableEducativa"):APP.index("function resaltarCartel")]
    detail = APP[APP.index("function renderSelectedVariableDetail"):APP.index("function renderEducationalState")]
    assert "fetch(" not in selection
    assert "fetchUltimasEducativas" not in selection
    assert "variable(clave)" in selection
    assert "variable(item.key)" in detail
    assert 'textContent=estado.formattedValue' in detail
    assert 'textContent=estado.unit' in detail
    assert 'textContent=colegioActual()' in detail
    assert 'textContent=nombresFuente[estado.source]' in detail
    assert 'textContent=item.explanation' in detail


def test_loading_no_data_error_and_missing_date_messages_are_explicit():
    for text in (
        "Cargando información…",
        "Sin datos disponibles",
        "Todavía no existe una medición de esta variable para el huerto seleccionado.",
        "No fue posible conectar con el servidor. Puedes intentar nuevamente con el botón Actualizar.",
        "Fecha no disponible",
    ):
        assert text in APP
    assert 'envolturaValor.hidden=estado.status!=="available"' in APP
    assert '$("#educational-detail-value").textContent=""' in APP


def test_school_change_and_refresh_preserve_selection_and_clear_old_values():
    school_change = APP[
        APP.index("function seleccionarLocalidad"):
        APP.index('document.querySelectorAll(".refresh").forEach(button=>button.onclick=cargar)')
    ]
    load = APP[APP.index("async function cargar()"):APP.index("function seleccionarLocalidad")]
    assert "selectedEducationalVariableKey" not in school_change
    assert "dashboard=estadoInicial()" in school_change
    assert "dashboard=estadoInicial()" in load
    assert "renderEducationalState()" in APP
    assert 'button.onclick=cargar' in APP
    assert "const ciclo=++cicloCarga,localidadSolicitada=localidad" in load


def test_keyboard_mobile_scroll_reduced_motion_and_responsive_layout_are_preserved():
    assert '<button type="button" class="sensor-card' in APP
    assert 'addEventListener("click",()=>resaltarCartel' in APP
    assert "ArrowRight" in APP and "ArrowLeft" in APP
    assert 'window.matchMedia("(max-width: 768px)").matches' in APP
    assert 'rect.top>=margenSuperior&&rect.bottom<=window.innerHeight' in APP
    assert 'window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"' in APP
    assert 'panel.scrollIntoView' in APP
    assert ".educational-detail{grid-template-columns:1fr" in CSS
    assert "overflow-wrap:anywhere" in CSS
    for viewport in (1440, 1024, 768, 390, 360):
        panel_width = viewport * (0.96 if viewport <= 760 else 0.94)
        assert panel_width <= viewport
