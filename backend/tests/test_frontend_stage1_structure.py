from hashlib import sha256
from pathlib import Path
import re
import struct
import zlib


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
HTML = (FRONTEND / "index.html").read_text(encoding="utf-8")
CSS = (FRONTEND / "css" / "estilos.css").read_text(encoding="utf-8")
APP = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
ORIGINAL_BACKGROUND = FRONTEND / "img" / "huerto-escena.png"
CLEAN_BACKGROUND = FRONTEND / "img" / "huerto-escolar-fondo-limpio.png"
CROPPED_BACKGROUND = FRONTEND / "img" / "huerto-escolar-limpio-recortado.png"
EXPECTED_BACKGROUND_SHA256 = "af5f587f9039b09c5665de405005a6027e12e184942b16eed9a70aab6d38a934"
EXPECTED_CLEAN_BACKGROUND_SHA256 = "9574bb63f1678ad48c2bee5bc3b13764a79ce5508819808d09e852382c09dfaa"
EXPECTED_CROPPED_BACKGROUND_SHA256 = "106118b6b34359b7ab2e73b21583aa0d7183bca26a7791eae57107c8c4dc3dc1"


def _png_dimensions(path: Path) -> tuple[int, int]:
    contents = path.read_bytes()
    assert contents.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", contents[16:24])


def _png_rgb_rows(path: Path) -> list[bytes]:
    contents = path.read_bytes()
    width, height = _png_dimensions(path)
    chunks: list[bytes] = []
    offset = 8
    while offset < len(contents):
        length = struct.unpack(">I", contents[offset:offset + 4])[0]
        kind = contents[offset + 4:offset + 8]
        payload = contents[offset + 8:offset + 8 + length]
        if kind == b"IHDR":
            assert payload[8:13] == bytes((8, 2, 0, 0, 0))
        elif kind == b"IDAT":
            chunks.append(payload)
        offset += length + 12
    raw = zlib.decompress(b"".join(chunks))
    stride, bytes_per_pixel = width * 3, 3
    rows: list[bytes] = []
    previous = bytearray(stride)
    cursor = 0

    def paeth(left: int, above: int, upper_left: int) -> int:
        estimate = left + above - upper_left
        distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
        return (left, above, upper_left)[distances.index(min(distances))]

    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor:cursor + stride])
        cursor += stride
        if filter_type == 1:
            for index in range(bytes_per_pixel, stride):
                row[index] = (row[index] + row[index - bytes_per_pixel]) & 255
        elif filter_type == 2:
            for index in range(stride):
                row[index] = (row[index] + previous[index]) & 255
        elif filter_type == 3:
            for index in range(stride):
                left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                row[index] = (row[index] + (left + previous[index]) // 2) & 255
        elif filter_type == 4:
            for index in range(stride):
                left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                row[index] = (row[index] + paeth(left, previous[index], upper_left)) & 255
        else:
            assert filter_type == 0
        rows.append(bytes(row))
        previous = row
    return rows


def test_clean_background_is_copied_without_altering_the_original() -> None:
    assert _png_dimensions(ORIGINAL_BACKGROUND) == (1736, 1946)
    assert sha256(ORIGINAL_BACKGROUND.read_bytes()).hexdigest() == EXPECTED_BACKGROUND_SHA256
    assert _png_dimensions(CLEAN_BACKGROUND) == (1186, 1327)
    assert sha256(CLEAN_BACKGROUND.read_bytes()).hexdigest() == EXPECTED_CLEAN_BACKGROUND_SHA256
    assert _png_dimensions(CROPPED_BACKGROUND) == (1186, 996)
    assert sha256(CROPPED_BACKGROUND.read_bytes()).hexdigest() == EXPECTED_CROPPED_BACKGROUND_SHA256
    assert _png_rgb_rows(CROPPED_BACKGROUND) == _png_rgb_rows(CLEAN_BACKGROUND)[265:1261]
    assert 'src="img/huerto-escolar-limpio-recortado.png"' in HTML
    assert 'src="img/huerto-escolar-fondo-limpio.png"' not in HTML
    assert ".codex/generated_images" not in HTML


def test_scene_has_ordered_accessible_layers_ready_for_stage_two() -> None:
    scene = HTML[HTML.index('<section class="huerto-scene"'):HTML.index("</section>", HTML.index('<section class="huerto-scene"'))]
    expected_order = (
        'class="huerto-scene__background"',
        'class="huerto-scene__connections"',
        'class="huerto-scene__markers"',
        'class="huerto-scene__cards"',
    )
    positions = [scene.index(fragment) for fragment in expected_order]
    assert positions == sorted(positions)
    assert re.search(r'<svg class="huerto-scene__connections"[^>]*></svg>', scene)
    assert '<div class="huerto-scene__markers"></div>' in scene
    assert '<div class="huerto-scene__cards" aria-label="Variables del huerto"></div>' in scene
    assert 'viewBox="0 0 100 100"' in scene
    assert 'aria-hidden="true" focusable="false"' in scene
    assert 'width="1186" height="996"' in scene
    assert 'alt="Huerto escolar en el paisaje andino"' in scene


def test_old_independent_scene_cards_lines_and_listeners_are_removed() -> None:
    for obsolete in (
        'id="hotspots"',
        'id="water-temperature-sign"',
        'id="water-temperature-value"',
        'id="water-temperature-date"',
        "crearHotspots",
        "actualizarCartelTemperaturaAgua",
        '$("#water-temperature-sign")',
        ".hotspot",
        ".water-temperature-sign",
        ".water-sign-copy",
    ):
        assert obsolete not in HTML + CSS + APP


def test_scene_is_responsive_without_rigid_dimensions_or_page_overflow() -> None:
    assert ".huerto-scene{position:relative;width:100%;max-width:100%;overflow:hidden" in CSS
    assert ".huerto-scene__background{position:relative;z-index:0;width:100%;height:auto;display:block}" in CSS
    assert ".huerto-scene__canvas{position:relative;width:100%;overflow:hidden}" in CSS
    assert ".huerto-scene__connections,.huerto-scene__markers{position:absolute;inset:0;width:100%;height:100%}" in CSS
    assert ".huerto-scene__connections{z-index:1;pointer-events:none}" in CSS
    for viewport in (1440, 1024, 768, 390, 360):
        scene_width = min(1380, viewport * (0.96 if viewport <= 760 else 0.94))
        scene_height = scene_width * 996 / 1186
        assert 0 < scene_width <= viewport
        assert 0 < scene_height < scene_width


def test_navigation_locality_data_and_history_code_are_preserved() -> None:
    for fragment in (
        'href="#explorar"',
        'href="#historial"',
        'id="localidades"',
        'id="research-categories"',
        'id="charts"',
    ):
        assert fragment in HTML
    for function_name in (
        "fetchUltimasEducativas",
        "fetchHistorialEducativo",
        "crearLocalidades",
        "seleccionarLocalidad",
        "crearGraficos",
        "cargarHistorialClaves",
    ):
        assert function_name in APP
