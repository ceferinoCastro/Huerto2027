from datetime import datetime
from pathlib import Path
from typing import Any


class HannaCSVError(ValueError):
    """Raised when an uploaded file is not a supported Hanna export."""


VARIABLES_DETECTED = ["pH", "conductividad eléctrica", "temperatura"]
VALUE_COLUMNS = {
    "ph_min": 2,
    "ph_max": 4,
    "ph_avg": 6,
    "ec_min_ms_cm": 8,
    "ec_max_ms_cm": 10,
    "ec_avg_ms_cm": 12,
    "temp_min_c": 14,
    "temp_max_c": 16,
    "temp_avg_c": 18,
}


def decode_hanna_file(content: bytes) -> str:
    """Decode tolerantly, then remove NULs before inspecting the export."""
    if not content:
        raise HannaCSVError("El archivo CSV está vacío")
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return (
            content.decode("utf-16", errors="replace")
            .replace("\x00", "")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )
    encodings = ["utf-8-sig", "cp1252", "latin-1"]
    candidates = [content.decode(encoding, errors="replace") for encoding in encodings]
    cleaned = [
        text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        for text in candidates
    ]
    return max(
        cleaned,
        key=lambda text: (
            sum(
                marker in text.casefold()
                for marker in ("date;time", "model;", "serial #;", "instrument id;")
            ),
            -text.count("\ufffd"),
        ),
    )


def parse_decimal(value: str) -> float | None:
    cleaned = value.replace(",", ".").strip()
    cleaned = cleaned.replace("!!", "").replace("\xa0", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date(value: str) -> datetime:
    for pattern in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), pattern)
        except ValueError:
            continue
    raise HannaCSVError(f"Fecha Hanna inválida: {value!r}")


def normalize_time(value: str) -> str:
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(value.strip(), pattern)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue
    raise HannaCSVError(f"Hora Hanna inválida: {value!r}")


def add_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def validate_values(
    values: dict[str, float | None],
    row_has_alert: bool,
) -> list[str]:
    reasons: list[str] = []
    if row_has_alert:
        add_reason(reasons, "marca !!")

    ph_average = values["ph_avg"]
    ec_average = values["ec_avg_ms_cm"]
    temp_average = values["temp_avg_c"]
    if ph_average is None:
        add_reason(reasons, "pH no numérico")
    elif ph_average <= 0 or ph_average > 14:
        add_reason(reasons, "pH fuera de rango")
    if ec_average is None:
        add_reason(reasons, "EC no numérica")
    elif ec_average < 0:
        add_reason(reasons, "EC fuera de rango")
    if temp_average is None:
        add_reason(reasons, "temperatura no numérica")
    elif temp_average <= 0 or temp_average >= 50:
        add_reason(reasons, "temperatura sospechosa")
    return reasons


def clean_cell(value: str) -> str:
    return value.strip().lstrip("\ufeff\ufffd").strip()


def diagnostic_preview(lines: list[str]) -> str:
    preview = []
    for index, line in enumerate(lines[:30], start=1):
        visible = line.strip().replace("\ufeff", "")[:200]
        preview.append(f"{index:02d}: {visible}")
    return "\n".join(preview)


def parse_hanna_metadata(content: bytes, filename: str) -> dict[str, str]:
    """Read Hanna identity fields without writing or importing measurements."""
    text = decode_hanna_file(content)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    metadata: dict[str, str] = {}
    header_index: int | None = None
    metadata_keys = {
        "model": "equipo_modelo",
        "serial #": "equipo_serial",
        "instrument id": "instrument_id",
    }
    for index, line in enumerate(lines):
        clean_line = line.strip().replace("\ufeff", "")
        cells = [clean_cell(cell) for cell in clean_line.split(";")]
        if cells:
            key = cells[0].casefold()
            if key in metadata_keys and len(cells) > 1:
                metadata[metadata_keys[key]] = cells[1]
        normalized = [cell.casefold() for cell in cells]
        if (
            len(cells) >= 20
            and normalized[0] == "date"
            and normalized[1] == "time"
            and "min" in normalized
            and "avg" in normalized
        ):
            header_index = index
            break

    if header_index is None:
        preview = diagnostic_preview(lines)
        raise HannaCSVError(
            "No se encontró la tabla Date;Time;Min;Unit del archivo Hanna. "
            f"Primeras 30 líneas limpias:\n{preview}"
        )
    if not metadata.get("equipo_serial"):
        raise HannaCSVError("No se encontró Serial # en el archivo Hanna")
    return {
        "archivo_nombre": Path(filename or "archivo.csv").name,
        "equipo_modelo": metadata.get("equipo_modelo", ""),
        "equipo_serial": metadata["equipo_serial"].strip().upper(),
        "instrument_id": metadata.get("instrument_id", ""),
        "header_index": str(header_index),
    }


def parse_hanna_csv(content: bytes, filename: str) -> dict[str, Any]:
    """Parse metadata and measurement rows from a Hanna HI981420 export."""
    identity = parse_hanna_metadata(content, filename)
    text = decode_hanna_file(content)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    header_index = int(identity.pop("header_index"))

    measurements: list[dict[str, Any]] = []
    for row_number, raw_line in enumerate(lines[header_index + 1 :], start=header_index + 2):
        clean_line = raw_line.strip().replace("\ufeff", "")
        row = [cell.strip() for cell in clean_line.split(";")]
        if not any(row):
            continue
        if len(row) < 20:
            continue
        try:
            day = parse_date(row[0])
            time_value = normalize_time(row[1])
        except HannaCSVError:
            continue
        values = {field: parse_decimal(row[index]) for field, index in VALUE_COLUMNS.items()}
        reasons = validate_values(values, "!!" in raw_line)
        date_value = day.strftime("%Y-%m-%d")
        measurements.append(
            {
                "fecha": date_value,
                "hora": time_value,
                "datetime_local": f"{date_value}T{time_value}",
                **values,
                "valido": not reasons,
                "motivos_alerta": reasons,
            }
        )

    if not measurements:
        raise HannaCSVError("El archivo Hanna no contiene filas de medición")
    return {
        **identity,
        "fecha_inicio": min(item["fecha"] for item in measurements),
        "fecha_fin": max(item["fecha"] for item in measurements),
        "variables_detectadas": VARIABLES_DETECTED.copy(),
        "mediciones": measurements,
    }
