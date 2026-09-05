from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "frontend2" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "frontend2" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "frontend2" / "api.js").read_text(encoding="utf-8")
HANNA_CSS = (ROOT / "frontend2" / "hanna.css").read_text(encoding="utf-8")
SERVER = (ROOT / "frontend2" / "servidor.py").read_text(encoding="utf-8")
CAMPAIGN_CSS = (ROOT / "frontend2" / "campaigns.css").read_text(encoding="utf-8")


def section(identifier: str) -> str:
    start = HTML.index(f'<section id="{identifier}"')
    later_views = [
        position
        for view in ("associations-view", "plants-view", "hanna-view", "campaigns-view")
        if (position := HTML.find(f'<section id="{view}"', start + 1)) != -1
    ]
    end = min(later_views) if later_views else len(HTML)
    return HTML[start:end]


def test_each_feature_owns_its_locality_selector() -> None:
    assert 'id="localidad"' in section("associations-view")
    assert 'id="plants-localidad"' in section("plants-view")
    hanna = section("hanna-view")
    assert 'id="hanna-colegio"' in hanna
    assert 'id="localidad"' not in hanna
    assert 'id="campaign-college"' in section("campaigns-view")


def test_hanna_preview_and_equipment_admin_are_wired() -> None:
    assert 'id="hanna-preview"' in HTML
    assert 'id="hanna-equipment-list"' in HTML
    assert "analizarCsvHanna" in APP
    assert "Corregir asignación" in APP
    assert "Reemplazar equipo" in APP
    assert '#hanna-college-field[hidden] { display: none; }' in HANNA_CSS


def test_hanna_upload_has_extended_proxy_timeout_and_structured_errors() -> None:
    assert "HANNA_IMPORT_TIMEOUT_SECONDS = 300" in SERVER
    assert 'self.path.startswith("/api/v1/mediciones-hanna/importar-csv")' in SERVER
    assert "self._send_json_error" in SERVER
    assert 'headers:{Accept:"application/json"}' in API


def test_campaign_ui_has_active_new_and_history_regions() -> None:
    campaigns = section("campaigns-view")
    for identifier in ("campaign-active", "campaign-form", "campaign-history"):
        assert f'id="{identifier}"' in campaigns
    assert "fetchCampaniaActiva" in APP
    assert "finalizarCampaniaActiva" in APP
    assert "cancelarCampaniaActiva" in APP


def test_new_campaign_button_is_permanent_and_only_active_state_blocks_it() -> None:
    campaigns = section("campaigns-view")
    assert 'id="campaign-new-trigger"' in campaigns
    assert "+ Nueva campaña" in campaigns
    assert "Para iniciar una nueva campaña, primero debe finalizar o cancelar la campaña activa." in campaigns
    assert 'class="panel campaign-new-panel" hidden' in campaigns
    assert 'item=>item.estado==="activa"' in APP
    assert 'active.item?.estado==="activa"' in APP
    assert "newButton.disabled=!campaignState.colegioId||blocked" in APP
    assert 'newPanel.hidden=(blocked&&campaignState.mode!=="edit")||!campaignState.formOpen' in APP
    assert "campaignState.formOpen=false;await cargarCampanias()" in APP
    assert "campaignState.formOpen=true;renderCampanias()" in APP


def test_new_admin_views_have_mobile_layouts() -> None:
    assert "@media (max-width: 680px)" in HANNA_CSS
    assert "@media (max-width: 680px)" in CAMPAIGN_CSS
    assert ".hanna-equipment-card { grid-template-columns: 1fr; }" in HANNA_CSS
    assert ".campaign-toolbar { align-items: stretch; flex-direction: column; }" in CAMPAIGN_CSS


def test_association_view_contains_real_poster_diagnostic_only_in_its_panel() -> None:
    associations = section("associations-view")
    assert 'id="poster-preview"' in associations
    assert "Vista previa de los carteles" in associations
    assert "Comprueba los datos que recibirá la interfaz infantil con las asociaciones actuales." in associations
    assert "Probar asociaciones" in associations
    for view in ("plants-view", "hanna-view", "campaigns-view"):
        assert 'id="poster-preview"' not in section(view)
    assert "fetchUltimasEducativas" in API
    assert 'variables-educativas/ultima' in API
    assert "fetchUltimasEducativas(localidad)" in APP
    assert "campania" not in APP[APP.index("function cargarVisorCarteles"):APP.index("async function cargarLocalidad")]


def test_poster_configuration_table_uses_the_backend_catalog_and_all_sources() -> None:
    associations = section("associations-view")
    assert "Configuración de carteles" in associations
    assert "Asociaciones existentes" not in associations
    for heading in (
        "Orden", "Variable educativa", "Fuente", "Sensor/equipo/origen",
        "Variable técnica/campo", "Estado", "Visible", "Acciones",
    ):
        assert f"<th>{heading}</th>" in associations
    assert "posterState.catalogo.map" in APP
    assert "const posterVariables=" not in APP
    assert 'source==="zentra"' in APP
    assert 'source==="hanna"' in APP
    assert "Medición de plantas" in APP
    assert "Sin equipo Hanna" in APP
    assert "Equipo asociado, sin mediciones" in APP
    assert "Disponible" in APP
    assert "Pendiente de asociar" in APP
    assert "Asociación incompleta" in APP
    assert "Asociado, sin datos" in APP
    assert "Eliminar asociación" in APP
    assert "data-associate" in APP
    assert "data-open-hanna" in APP
    assert "data-open-plants" in APP
    assert 'rows.length+" carteles · "+configured+" configurados · "+pending+" pendientes"' in APP


def test_changing_college_clears_old_configuration_before_loading() -> None:
    locality_loader = APP[APP.index("async function cargarLocalidad"):APP.index("function crearCamposPlantas")]
    clear_at = locality_loader.index("state.asociaciones=[]")
    load_at = locality_loader.index("fetchColegios()")
    assert clear_at < load_at
    assert "posterState.items=[]" in locality_loader[:load_at]
    assert "posterState.catalogo=[]" in locality_loader[:load_at]
    assert "state.cargandoConfiguracion=true" in locality_loader[:load_at]
    assert "renderAsociaciones();cargarVisorCarteles()" in locality_loader[:load_at]


def test_configuration_table_is_contained_on_mobile_and_api_notice_is_current() -> None:
    styles = (ROOT / "frontend2" / "styles.css").read_text(encoding="utf-8")
    associations = section("associations-view")
    assert ".table-panel { min-width: 0;" in styles
    assert ".table-scroll { max-width: 100%; overflow-x: auto;" in styles
    assert "FastAPI todavía no implementa los endpoints de asociaciones" not in associations
    assert "No fue posible consultar las asociaciones Zentra." in associations
    assert 'id="endpoint-notice-detail"' in associations
    assert 'id="retry-associations"' in associations
    assert ".endpoint-notice[hidden] { display: none; }" in styles


def test_association_api_availability_is_separate_from_configuration_states() -> None:
    for state_name in (
        "apiAsociacionesDisponible", "cargandoAsociaciones", "asociacionesVacias",
        "errorConsultaAsociaciones", "errorOperacionAsociacion",
    ):
        assert state_name in APP
    assert "crudDisponible" not in APP
    assert 'notice.hidden=state.apiAsociacionesDisponible!==false' in APP
    assert 'state.apiAsociacionesDisponible=true' in APP
    assert 'state.apiAsociacionesDisponible=false' in APP
    assert 'state.asociacionesVacias=!state.asociaciones.some' in APP
    assert "API disponible · Sin asociaciones Zentra para este colegio" in APP
    assert 'const disabled=apiDisponible?"":" disabled"' in APP


def test_association_errors_retry_and_stale_requests_are_handled_independently() -> None:
    loader = APP[APP.index("async function consultarAsociaciones"):APP.index("async function cargarLocalidad")]
    assert "Array.isArray(data.items)" in loader
    assert "La respuesta no contiene una lista de asociaciones utilizable" in loader
    assert "carga!==state.carga||localidad!==state.localidad" in loader
    assert "Error HTTP " in APP
    assert "reintentarAsociaciones" in loader
    assert '$("#retry-associations").onclick=reintentarAsociaciones' in APP
    assert "No fue posible guardar la asociación." in loader
    assert "No fue posible eliminar la asociación." in loader
    assert "await consultarAsociaciones()" in loader
    poster_loader = APP[APP.index("async function cargarVisorCarteles"):APP.index("function setStatus")]
    assert "apiAsociacionesDisponible" not in poster_loader


def test_json_contract_errors_have_an_explicit_message() -> None:
    assert "const body=await response.text()" in API
    assert 'JSON.parse(body)' in API
    assert "FastAPI devolvió una respuesta JSON inválida" in API


def test_poster_diagnostic_covers_states_details_refresh_and_mobile() -> None:
    assert "posterState.catalogo" in APP
    for text in (
        "Cargando...", "Dato real", "Variable sin sensor asociado",
        "Sensor asociado, pero sin mediciones", "No fue posible consultar esta medición",
        "Ver detalle técnico", "No informado",
    ):
        assert text in APP or text in HTML
    for field in (
        "clave_educativa", "colegio_id", "coleccion", "device_sn", "sensor_sn",
        "sensor_modelo", "variable_tecnica", "campo_consultado", "unidad_original",
        "fecha_original", "estado_asociacion", "serial_hanna", "modelo", "instrument_id",
    ):
        assert field in APP
    assert '$("#test-associations").disabled=true' in APP
    assert '$("#test-associations").onclick=cargarVisorCarteles' in APP
    assert "posterState.carga++" in APP
    assert 'item.estado==="sin_equipo_hanna"?"sin_asociacion"' in APP
    assert 'item.estado==="sin_datos_validos"?"sin_datos"' in APP
    assert "cargarVisorCarteles(true)" in APP
    assert "await cargarLocalidad(\"guardado\")" in APP
    assert "await cargarLocalidad(\"eliminado\")" in APP
    assert ".poster-preview-grid { grid-template-columns: 1fr; }" in (ROOT / "frontend2" / "styles.css").read_text(encoding="utf-8")
    assert "Dato demostrativo" not in section("associations-view")
