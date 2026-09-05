import json
from pathlib import Path
import re
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


def _catalog_data() -> list[dict]:
    script = (
        f'import {{SENSOR_CARD_CATALOG}} from {json.dumps(CATALOG_PATH.as_uri())};'
        'console.log(JSON.stringify(SENSOR_CARD_CATALOG));'
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _group_data() -> list[dict]:
    script = (
        f'import {{SENSOR_GROUP_CATALOG}} from {json.dumps(CATALOG_PATH.as_uri())};'
        'console.log(JSON.stringify(SENSOR_GROUP_CATALOG));'
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _crop_data() -> dict:
    script = (
        f'import {{BACKGROUND_CROP}} from {json.dumps(CATALOG_PATH.as_uri())};'
        'console.log(JSON.stringify(BACKGROUND_CROP));'
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_catalog_has_exactly_eleven_ordered_unique_cards() -> None:
    items = _catalog_data()
    assert len(items) == 11
    assert [item["key"] for item in items] == EXPECTED_KEYS
    assert len({item["key"] for item in items}) == 11
    assert '<button class="sensor-card' not in HTML
    assert "SENSOR_CARD_CATALOG.filter" in APP


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
    assert len(visible) == 8
    assert max(lengths) <= 25
    air = [item for item in items if item["group"] == "air"]
    water = [item for item in items if item["group"] == "water"]
    assert {item["sharedTarget"] for item in air} == {"atmosphere"}
    assert {item["sharedTarget"] for item in water} == {"pond"}
    assert sum(item["showConnection"] for item in air) == 1
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
    original_positions = {
        "temperatura_aire": (39, 24),
        "humedad_aire": (58, 24),
        "humedad_hojas": (66, 36),
        "temperatura_tierra": (40, 48),
        "temperatura_bajo_tierra": (38, 76),
        "humedad_tierra": (64, 76),
        "ph_agua": (8, 50),
        "sales_agua": (8, 57),
        "temperatura_agua": (8, 64),
        "altura_planta": (73, 47),
        "largo_raiz": (51, 76),
    }
    expected = {
        key: {"x": x, "y": round(((y - 20) / 75) * 100, 4)}
        for key, (x, y) in original_positions.items()
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


def test_every_scene_y_coordinate_was_transformed_for_the_crop() -> None:
    original = {
        "temperatura_aire": (24, 32, [28]),
        "humedad_aire": (24, 32, []),
        "humedad_hojas": (36, 47, [42]),
        "temperatura_tierra": (48, 59, [54]),
        "temperatura_bajo_tierra": (76, 69, [72]),
        "humedad_tierra": (76, 68, [72]),
        "ph_agua": (50, 75, []),
        "sales_agua": (57, 75, []),
        "temperatura_agua": (64, 75, [70]),
        "altura_planta": (47, 43.5, [45]),
        "largo_raiz": (76, 72, [73]),
    }
    transform = lambda value: round(((value - 20) / 75) * 100, 4)
    for item in _catalog_data():
        position_y, target_y, route_ys = original[item["key"]]
        assert item["position"]["desktop"]["y"] == transform(position_y)
        assert item["target"]["y"] == transform(target_y)
        assert [point["y"] for point in item["route"]] == [transform(value) for value in route_ys]
    rulers = {item["key"]: item["ruler"] for item in _catalog_data() if item.get("ruler")}
    assert rulers["altura_planta"]["y1"] == transform(59)
    assert rulers["altura_planta"]["y2"] == transform(43.5)
    assert rulers["largo_raiz"]["y1"] == transform(59)
    assert rulers["largo_raiz"]["y2"] == transform(74.5)


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


def test_stage_two_adds_no_backend_request_and_preserves_existing_features() -> None:
    assert "fetch(" not in CATALOG
    assert "fetch(" not in APP
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
