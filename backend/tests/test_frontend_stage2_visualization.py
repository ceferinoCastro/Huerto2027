import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
HTML = (FRONTEND / "index.html").read_text(encoding="utf-8")
CSS = (FRONTEND / "css" / "estilos.css").read_text(encoding="utf-8")
APP = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
CATALOG_PATH = FRONTEND / "js" / "catalogo-carteles.js"
CATALOG = CATALOG_PATH.read_text(encoding="utf-8")

EXPECTED_KEYS = [
    "temperatura_aire",
    "humedad_aire",
    "humedad_hojas",
    "temperatura_tierra",
    "temperatura_bajo_tierra",
    "humedad_tierra",
    "ph_agua",
    "sales_agua",
    "temperatura_agua",
    "altura_planta",
    "largo_raiz",
]

# Réplica exacta de los 11 carteles fijos, con la forma que devuelve
# GET /api/v1/carteles (ver backend/app/models/carteles.py y
# backend/scripts/migrate_educational_posters.py::_VISUAL_SEED), usada para
# simular la respuesta del backend sin depender de una base de datos real.
BACKEND_ITEMS = [
    {"clave_educativa": "temperatura_aire", "nombre_educativo": "Temperatura del aire", "unidad": "°C",
     "fuente_sugerida": "zentra", "icono": "temperature", "grupo_visual": "air", "compartir_conexion_con": "atmosphere",
     "mostrar_conexion": True, "posicion_x": 39, "posicion_y": 25.3333, "destino_x": 49, "destino_y": 16,
     "destino_zona": "aire sobre el huerto", "ruta_punto1_x": 44, "ruta_punto1_y": 15, "ancla": "bottom",
     "etiqueta_corta": "T° del aire", "explicacion": "Indica qué tan cálido o frío está el aire alrededor de las plantas."},
    {"clave_educativa": "humedad_aire", "nombre_educativo": "Agua en el aire", "unidad": "%",
     "fuente_sugerida": "zentra", "icono": "humidity", "grupo_visual": "air", "compartir_conexion_con": "atmosphere",
     "mostrar_conexion": True, "posicion_x": 25, "posicion_y": 25.3333, "destino_x": 49, "destino_y": 16,
     "destino_zona": "aire sobre el huerto", "ruta_punto1_x": 52, "ruta_punto1_y": 12, "ancla": "bottom",
     "etiqueta_corta": "Agua en el aire", "explicacion": "Muestra cuánta humedad contiene el aire que rodea el huerto."},
    {"clave_educativa": "humedad_hojas", "nombre_educativo": "Agua en hojas", "unidad": "%",
     "fuente_sugerida": "zentra", "icono": "leaf-water", "grupo_visual": "plant", "compartir_conexion_con": None,
     "mostrar_conexion": True, "posicion_x": 66, "posicion_y": 21.3333, "destino_x": 60, "destino_y": 36,
     "destino_zona": "hojas de la planta", "ruta_punto1_x": 62, "ruta_punto1_y": 29.3333, "ancla": "left",
     "etiqueta_corta": "Agua en hojas", "explicacion": "Indica si las hojas se encuentran secas o tienen agua sobre su superficie."},
    {"clave_educativa": "temperatura_tierra", "nombre_educativo": "Temperatura de la tierra", "unidad": "°C",
     "fuente_sugerida": "zentra", "icono": "temperature-soil", "grupo_visual": "earth", "compartir_conexion_con": None,
     "mostrar_conexion": True, "posicion_x": 40, "posicion_y": 37.3333, "destino_x": 44, "destino_y": 52,
     "destino_zona": "superficie de la tierra", "ruta_punto1_x": 42, "ruta_punto1_y": 45.3333, "ancla": "bottom",
     "etiqueta_corta": "T° de la tierra", "explicacion": "Muestra la temperatura de la superficie de la tierra del huerto."},
    {"clave_educativa": "temperatura_bajo_tierra", "nombre_educativo": "Temperatura bajo tierra", "unidad": "°C",
     "fuente_sugerida": "zentra", "icono": "temperature-depth", "grupo_visual": "earth", "compartir_conexion_con": None,
     "mostrar_conexion": True, "posicion_x": 38, "posicion_y": 74.6667, "destino_x": 42, "destino_y": 65.3333,
     "destino_zona": "interior profundo izquierdo del cajón", "ruta_punto1_x": 40, "ruta_punto1_y": 69.3333, "ancla": "top",
     "etiqueta_corta": "T° bajo tierra", "explicacion": "Muestra la temperatura en la zona profunda de la tierra, cerca de las raíces."},
    {"clave_educativa": "humedad_tierra", "nombre_educativo": "Agua en tierra", "unidad": "%",
     "fuente_sugerida": "zentra", "icono": "soil-water", "grupo_visual": "earth", "compartir_conexion_con": None,
     "mostrar_conexion": True, "posicion_x": 64, "posicion_y": 74.6667, "destino_x": 63, "destino_y": 64,
     "destino_zona": "volumen profundo derecho de tierra", "ruta_punto1_x": 63.5, "ruta_punto1_y": 69.3333, "ancla": "top",
     "etiqueta_corta": "Agua en tierra", "explicacion": "Indica cuánta agua hay disponible en la tierra para las raíces."},
    {"clave_educativa": "ph_agua", "nombre_educativo": "pH del agua", "unidad": "pH",
     "fuente_sugerida": "hanna", "icono": "ph-water", "grupo_visual": "water", "compartir_conexion_con": "pond",
     "mostrar_conexion": False, "posicion_x": 8, "posicion_y": 40, "destino_x": 12, "destino_y": 73.3333,
     "destino_zona": "estanque verde", "ancla": "bottom",
     "etiqueta_corta": "pH del agua", "explicacion": "Indica si el agua es más ácida, neutra o alcalina."},
    {"clave_educativa": "sales_agua", "nombre_educativo": "Sales del agua", "unidad": "mS/cm",
     "fuente_sugerida": "hanna", "icono": "salts-water", "grupo_visual": "water", "compartir_conexion_con": "pond",
     "mostrar_conexion": False, "posicion_x": 8, "posicion_y": 49.3333, "destino_x": 12, "destino_y": 73.3333,
     "destino_zona": "estanque verde", "ancla": "bottom",
     "etiqueta_corta": "Sales del agua", "explicacion": "Muestra la cantidad de sales presentes en el agua del estanque."},
    {"clave_educativa": "temperatura_agua", "nombre_educativo": "Temperatura del agua", "unidad": "°C",
     "fuente_sugerida": "hanna", "icono": "temperature-water", "grupo_visual": "water", "compartir_conexion_con": "pond",
     "mostrar_conexion": True, "posicion_x": 8, "posicion_y": 58.6667, "destino_x": 12, "destino_y": 73.3333,
     "destino_zona": "estanque verde", "ruta_punto1_x": 10, "ruta_punto1_y": 66.6667, "ancla": "bottom",
     "etiqueta_corta": "T° del agua", "explicacion": "Indica qué tan fría o cálida está el agua almacenada en el estanque."},
    {"clave_educativa": "altura_planta", "nombre_educativo": "Alto de planta", "unidad": "cm",
     "fuente_sugerida": "manual", "icono": "plant-height", "grupo_visual": "plant", "compartir_conexion_con": None,
     "mostrar_conexion": True, "posicion_x": 73, "posicion_y": 36, "destino_x": 64.5, "destino_y": 31.3333,
     "destino_zona": "parte superior de la planta", "ruta_punto1_x": 66, "ruta_punto1_y": 33.3333, "ancla": "left",
     "etiqueta_corta": "Alto de planta", "explicacion": "Muestra cuánto ha crecido la planta desde la superficie de la tierra.",
     "regla": {"id": "plant-height-ruler", "label": "Regla para medir el alto de la planta",
               "x": 64.5, "y1": 52, "y2": 31.3333, "tickSide": "right"}},
    {"clave_educativa": "largo_raiz", "nombre_educativo": "Largo de raíz", "unidad": "cm",
     "fuente_sugerida": "manual", "icono": "root-length", "grupo_visual": "earth", "compartir_conexion_con": None,
     "mostrar_conexion": True, "posicion_x": 51, "posicion_y": 74.6667, "destino_x": 53, "destino_y": 69.3333,
     "destino_zona": "raíz principal visible", "ruta_punto1_x": 52, "ruta_punto1_y": 70.6667, "ancla": "top",
     "etiqueta_corta": "Largo de raíz", "explicacion": "Muestra cuánto ha crecido la raíz principal bajo la tierra.",
     "regla": {"id": "root-length-ruler", "label": "Regla para medir el largo de la raíz",
               "x": 58, "y1": 52, "y2": 72.6667, "tickSide": "right"}},
]

# Carteles sin coordenadas: deben ser ignorados por el filtro del frontend público.
INCOMPLETE_ITEMS = [
    {"clave_educativa": "sin_posicion", "nombre_educativo": "Sin posición", "unidad": "u",
     "fuente_sugerida": "manual", "destino_x": 10, "destino_y": 10},
    {"clave_educativa": "sin_destino", "nombre_educativo": "Sin destino", "unidad": "u",
     "fuente_sugerida": "manual", "posicion_x": 10, "posicion_y": 10},
]


def _run_node(script: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _cargar_catalogo_visual(items: list[dict]) -> list[dict]:
    """Simula la respuesta de GET /api/v1/carteles y ejecuta cargarCatalogoVisual()."""
    script = (
        f'globalThis.fetch=async()=>({{ok:true,json:async()=>({json.dumps({"items": items})})}});'
        f'import {{cargarCatalogoVisual}} from {json.dumps(CATALOG_PATH.as_uri())};'
        'const items=await cargarCatalogoVisual();console.log(JSON.stringify(items));'
    )
    return _run_node(script)


def _catalog_data() -> list[dict]:
    return _cargar_catalogo_visual(BACKEND_ITEMS)


def _group_data() -> list[dict]:
    script = (
        f'import {{SENSOR_GROUP_CATALOG}} from {json.dumps(CATALOG_PATH.as_uri())};'
        'console.log(JSON.stringify(SENSOR_GROUP_CATALOG));'
    )
    return _run_node(script)


def _crop_data() -> dict:
    script = (
        f'import {{BACKGROUND_CROP}} from {json.dumps(CATALOG_PATH.as_uri())};'
        'console.log(JSON.stringify(BACKGROUND_CROP));'
    )
    return _run_node(script)


def test_dynamic_catalog_fetches_the_carteles_endpoint_and_maps_the_backend_shape() -> None:
    assert "export async function cargarCatalogoVisual" in CATALOG
    assert 'fetch("/api/v1/carteles")' in CATALOG
    assert "SENSOR_CARD_CATALOG" not in CATALOG
    items = _catalog_data()
    assert len(items) == 11
    assert [item["key"] for item in items] == EXPECTED_KEYS
    assert len({item["key"] for item in items}) == 11


def test_carteles_without_full_coordinates_are_filtered_out_and_do_not_break_loading() -> None:
    items = _cargar_catalogo_visual(BACKEND_ITEMS + INCOMPLETE_ITEMS)
    assert len(items) == 11
    assert "sin_posicion" not in {item["key"] for item in items}
    assert "sin_destino" not in {item["key"] for item in items}


def test_carteles_with_visible_frontend_false_are_hidden_from_the_public_scene() -> None:
    ocultos = [
        {**BACKEND_ITEMS[0], "clave_educativa": "oculto_explicito", "visible_frontend": False},
    ]
    items = _cargar_catalogo_visual(BACKEND_ITEMS + ocultos)
    assert len(items) == 11
    assert "oculto_explicito" not in {item["key"] for item in items}


def test_carteles_without_the_visible_frontend_field_default_to_visible() -> None:
    legado = [{**BACKEND_ITEMS[0], "clave_educativa": "legado_sin_campo"}]
    for item in legado:
        item.pop("visible_frontend", None)
    items = _cargar_catalogo_visual(BACKEND_ITEMS + legado)
    assert "legado_sin_campo" in {item["key"] for item in items}


def test_public_app_loads_the_catalog_asynchronously_before_drawing_and_has_a_fallback() -> None:
    assert "cargarCatalogoVisual" in APP
    assert "SENSOR_CARD_CATALOG.filter" in APP
    assert "async function iniciar" in APP
    assert "await cargarCatalogoVisual()" in APP
    assert "async function actualizarCatalogoVisual" in APP
    assert "catch" in APP[APP.index("async function actualizarCatalogoVisual"):APP.index("async function cargar()")]
    assert "await actualizarCatalogoVisual()" in APP
    assert '<button class="sensor-card' not in HTML


def test_catalog_has_complete_visual_state_and_percentage_coordinates() -> None:
    items = _catalog_data()
    group_orders = {"air": [], "plant": [], "earth": [], "water": []}
    for item in items:
        assert item["label"]
        assert item["explanation"]
        assert item["shortLabel"]
        assert item["icon"]
        assert item["unit"]
        assert item["source"] in {"zentra", "hanna", "manual"}
        assert item["group"] in group_orders
        group_orders[item["group"]].append(item["position"]["mobile"]["order"])
        for point in (item["position"]["desktop"], item["target"]):
            assert 0 <= point["x"] <= 100
            assert 0 <= point["y"] <= 100
        assert item["target"]["zone"]
        assert item["anchor"] in {"top", "right", "bottom", "left"}
    for orders in group_orders.values():
        assert sorted(orders) == list(range(1, len(orders) + 1))


def test_catalog_source_families_match_the_educational_model() -> None:
    items = _catalog_data()
    assert [item["key"] for item in items if item["source"] == "zentra"] == EXPECTED_KEYS[:6]
    assert [item["key"] for item in items if item["source"] == "hanna"] == EXPECTED_KEYS[6:9]
    assert [item["key"] for item in items if item["source"] == "manual"] == EXPECTED_KEYS[9:]


def test_four_visual_groups_have_the_required_members() -> None:
    items = _catalog_data()
    groups = _group_data()
    assert [group["key"] for group in groups] == ["air", "plant", "earth", "water"]
    assert [group["label"] for group in groups] == ["Aire", "Planta", "Tierra y raíces", "Agua del estanque"]
    memberships = {group["key"]: [item["key"] for item in items if item["group"] == group["key"]] for group in groups}
    assert memberships["air"] == ["temperatura_aire", "humedad_aire"]
    assert memberships["plant"] == ["humedad_hojas", "altura_planta"]
    assert memberships["earth"] == ["temperatura_tierra", "temperatura_bajo_tierra", "humedad_tierra", "largo_raiz"]
    assert memberships["water"] == ["ph_agua", "sales_agua", "temperatura_agua"]


def test_all_cards_use_one_neutral_component_without_demo_values() -> None:
    assert 'data-status="'+"estado.status" not in HTML
    assert "Sin conectar" not in APP
    assert "Cargando…" in APP
    assert 'class="sensor-card sensor-card--neutral"' in APP
    assert "item.label" in APP and "iconoCartel(item.icon)" in APP
    rendered_component = APP[APP.index("carteles.innerHTML="):APP.index("document.querySelectorAll(\"[data-sensor-marker]\")")]
    for fictitious in ("24.6", "64.4", "11.8", "32.8", "6.34", "18.4"):
        assert fictitious not in rendered_component


def test_scalable_connections_and_targets_are_derived_from_the_catalog() -> None:
    items = _catalog_data()
    assert len([item["target"] for item in items]) == 11
    assert 'viewBox="0 0 100 100"' in HTML
    assert "puntoAnclaje(item)" in APP
    assert "trazadoConexion(item)" in APP
    assert "item.target.x" in APP and "item.target.y" in APP
    assert '<g class="sensor-connection" data-sensor-target="' in APP
    assert "const objetivos=[...SENSOR_CARD_CATALOG.reduce" in APP
    assert "vector-effect:non-scaling-stroke" in CSS
    assert ".huerto-scene__connections{z-index:1;overflow:visible;pointer-events:none}" in CSS


def test_connections_are_short_and_shared_where_appropriate() -> None:
    items = _catalog_data()
    visible = [item for item in items if item["showConnection"]]
    lengths = [
        ((item["position"]["desktop"]["x"] - item["target"]["x"]) ** 2 +
         (item["position"]["desktop"]["y"] - item["target"]["y"]) ** 2) ** 0.5
        for item in visible
    ]
    assert len(visible) == 9
    assert max(lengths) <= 26
    air = [item for item in items if item["group"] == "air"]
    water = [item for item in items if item["group"] == "water"]
    assert {item["sharedTarget"] for item in air} == {"atmosphere"}
    assert {item["sharedTarget"] for item in water} == {"pond"}
    assert sum(item["showConnection"] for item in air) == 2
    assert sum(item["showConnection"] for item in water) == 1


def test_targets_represent_the_required_conceptual_zones() -> None:
    zones = {item["key"]: item["target"]["zone"] for item in _catalog_data()}
    assert zones["temperatura_aire"] == zones["humedad_aire"] == "aire sobre el huerto"
    assert zones["humedad_hojas"] == "hojas de la planta"
    assert zones["temperatura_tierra"] == "superficie de la tierra"
    assert zones["temperatura_bajo_tierra"] == "interior profundo izquierdo del cajón"
    assert zones["humedad_tierra"] == "volumen profundo derecho de tierra"
    assert {zones[key] for key in EXPECTED_KEYS[6:9]} == {"estanque verde"}
    assert zones["altura_planta"] == "parte superior de la planta"
    assert zones["largo_raiz"] == "raíz principal visible"
    targets = {item["key"]: (item["target"]["x"], item["target"]["y"]) for item in _catalog_data()}
    assert targets["humedad_hojas"] != targets["altura_planta"]
    assert len({targets[key] for key in ("temperatura_tierra", "humedad_tierra", "temperatura_bajo_tierra", "largo_raiz")}) == 4


def test_mockup_positions_and_lower_row_order_are_centralized() -> None:
    positions = {item["key"]: item["position"]["desktop"] for item in _catalog_data()}
    expected = {
        item["clave_educativa"]: {"x": item["posicion_x"], "y": item["posicion_y"]}
        for item in BACKEND_ITEMS
    }
    assert positions == expected
    lower_row = sorted(
        (positions[key]["x"], key)
        for key in ("temperatura_bajo_tierra", "largo_raiz", "humedad_tierra")
    )
    assert [key for _x, key in lower_row] == ["temperatura_bajo_tierra", "largo_raiz", "humedad_tierra"]
    assert {positions[key]["y"] for _x, key in lower_row} == {74.6667}


def test_crop_constants_and_css_percentage_mapping_are_explicit() -> None:
    assert _crop_data() == {
        "originalHeight": 1327,
        "topPixels": 265,
        "bottomPixels": 66,
        "visibleHeight": 996,
        "topPercent": 20,
        "visiblePercent": 75,
    }
    assert "left:calc(var(--card-x)*1%)" in CSS
    assert "top:calc(var(--card-y)*1%)" in CSS


def test_every_scene_coordinate_matches_the_backend_metadata_exactly() -> None:
    by_key = {item["clave_educativa"]: item for item in BACKEND_ITEMS}
    for item in _catalog_data():
        source = by_key[item["key"]]
        assert item["position"]["desktop"]["y"] == source["posicion_y"]
        assert item["target"]["y"] == source["destino_y"]
        expected_route = []
        if source.get("ruta_punto1_x") is not None:
            expected_route.append(source["ruta_punto1_y"])
        if source.get("ruta_punto2_x") is not None:
            expected_route.append(source["ruta_punto2_y"])
        assert [point["y"] for point in item["route"]] == expected_route
    rulers = {item["key"]: item["ruler"] for item in _catalog_data() if item.get("ruler")}
    assert rulers["altura_planta"] == by_key["altura_planta"]["regla"]
    assert rulers["largo_raiz"] == by_key["largo_raiz"]["regla"]


def test_independent_plant_and_root_rulers_have_ticks_without_fake_values() -> None:
    rulers = {item["key"]: item["ruler"] for item in _catalog_data() if item.get("ruler")}
    assert set(rulers) == {"altura_planta", "largo_raiz"}
    assert rulers["altura_planta"]["id"] == "plant-height-ruler"
    assert rulers["altura_planta"]["label"] == "Regla para medir el alto de la planta"
    assert rulers["altura_planta"]["y1"] > rulers["altura_planta"]["y2"]
    assert rulers["largo_raiz"]["id"] == "root-length-ruler"
    assert rulers["largo_raiz"]["label"] == "Regla para medir el largo de la raíz"
    assert rulers["largo_raiz"]["y1"] < rulers["largo_raiz"]["y2"]
    assert "function reglaMedicion(item)" in APP
    assert "Array.from({length:7}" in APP
    ruler_renderer = APP[APP.index("function reglaMedicion"):APP.index("function clavesElemento")]
    assert "<text" not in ruler_renderer
    assert 'class="sensor-ruler__spine"' in APP
    assert 'class="sensor-ruler__tick"' in APP
    assert ".sensor-ruler__spine,.sensor-ruler__tick" in CSS
    assert 'descripcionRegla=item.ruler?' in APP


def test_mobile_layout_hides_lines_and_moves_cards_below_image() -> None:
    assert "@media(max-width:768px)" in CSS
    assert ".huerto-scene__connections{display:none}" in CSS
    assert ".huerto-scene__cards{position:relative;inset:auto" in CSS
    assert ".sensor-group{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in CSS
    assert "SENSOR_GROUP_CATALOG.map" in APP
    assert 'class="sensor-group__title"' in APP
    assert HTML.index('class="huerto-scene__canvas"') < HTML.index('class="huerto-scene__cards"')
    assert "min-width:0" in CSS
    for viewport in (1440, 1024, 768, 390, 360):
        scene_width = min(1380, viewport * (0.96 if viewport <= 760 else 0.94))
        assert scene_width <= viewport


def test_mobile_markers_are_accessible_and_interact_with_cards() -> None:
    assert "aria-label=\"Ver '+etiqueta+'\"" in APP
    assert 'data-sensor-marker="' in APP
    assert "resaltarMarcador(marcador)" in APP
    assert "resaltarCartel(cartel.dataset.sensorCard,{desplazar:true})" in APP
    assert "scrollIntoView" in APP
    assert "focus({preventScroll:true})" in APP
    assert all(key not in HTML for key in EXPECTED_KEYS)


def test_keyboard_focus_and_reduced_motion_are_supported() -> None:
    assert '<button type="button" class="sensor-card' in APP
    assert '<button type="button" class="sensor-marker' in APP
    assert "ArrowRight" in APP and "ArrowDown" in APP
    assert "ArrowLeft" in APP and "ArrowUp" in APP
    assert 'evento.key==="Escape"' in APP
    assert 'evento.target.closest("[data-sensor-card],[data-sensor-marker]")' in APP
    assert ":focus-visible" in CSS
    assert "@media(prefers-reduced-motion:reduce)" in CSS


def test_selection_emphasizes_target_and_softens_other_cards() -> None:
    assert "function aplicarResaltado(claves)" in APP
    assert 'classList.toggle("is-highlighted",coincide)' in APP
    assert 'classList.toggle("is-muted",!coincide)' in APP
    assert ".huerto-scene.has-sensor-selection .sensor-card.is-muted{opacity:.52" in CSS
    assert ".sensor-connection.is-highlighted path{stroke-width:3;opacity:1}" in CSS
    assert "function restaurarCarteles()" in APP


def test_stage_two_preserves_existing_dashboard_features() -> None:
    assert APP.count("fetchUltimasEducativas") == 2
    assert APP.count("fetchHistorialEducativo") == 2
    for function_name in ("crearLocalidades", "seleccionarLocalidad", "crearGraficos", "cargarHistorialClaves"):
        assert function_name in APP
    for element_id in ("localidades", "research-categories", "educational-detail-panel", "charts"):
        assert f'id="{element_id}"' in HTML


def test_cards_remain_inside_desktop_scene_bounds() -> None:
    for item in _catalog_data():
        x = item["position"]["desktop"]["x"]
        y = item["position"]["desktop"]["y"]
        assert 7 <= x <= 93
        assert 4 <= y <= 96
    assert ".huerto-scene{position:relative;width:100%;max-width:100%;overflow:hidden" in CSS
