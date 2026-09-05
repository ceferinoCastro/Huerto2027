from datetime import datetime

from pydantic import BaseModel


class HannaImportResponse(BaseModel):
    ok: bool = True
    localidad: str
    archivo_nombre: str
    equipo_modelo: str
    equipo_serial: str
    instrument_id: str
    fecha_inicio: str
    fecha_fin: str
    registros_leidos: int
    insertados: int
    actualizados: int
    duplicados: int
    validos: int
    invalidos: int
    variables_detectadas: list[str]


class HannaPreviewResponse(BaseModel):
    archivo_nombre: str
    modelo: str
    serial_hanna: str
    instrument_id: str
    asociado: bool
    equipo: dict | None = None
    mensaje: str


class HannaSummaryResponse(BaseModel):
    localidad: str
    ultima_carga: datetime | None = None
    archivos_cargados: int = 0
    total_registros: int = 0
    total_validos: int = 0
    total_invalidos: int = 0
    fecha_minima: str | None = None
    fecha_maxima: str | None = None
    equipo_serial: str | None = None


class HannaSeriesItem(BaseModel):
    fecha: str
    valor: float


class HannaSeriesResponse(BaseModel):
    localidad: str
    variable: str
    nombre: str
    unidad: str
    items: list[HannaSeriesItem]


class HannaLatestResponse(BaseModel):
    colegio_id: str | None = None
    localidad: str
    variable: str
    nombre: str
    valor: float | None = None
    unidad: str
    fecha: str | None = None
    hora: str | None = None
    datetime_local: str | None = None
    mensaje: str | None = None
    fuente: str = "hanna"
    serial_hanna: str | None = None
    modelo: str | None = None
    instrument_id: str | None = None
    estado: str = "ok"
