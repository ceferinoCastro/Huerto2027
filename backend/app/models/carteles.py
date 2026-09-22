from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssociationSourceHint = Literal["zentra", "hanna", "manual"]


class CartelInput(BaseModel):
    """Cartel educativo: lo que ve un estudiante, desacoplado de su sensor real."""

    model_config = ConfigDict(extra="forbid")

    clave_educativa: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    nombre_educativo: str = Field(min_length=1, max_length=160)
    unidad: str = Field(max_length=40)
    categoria: str = Field(default="", max_length=80)
    orden: int = Field(default=1, ge=0, le=1000)
    visible_frontend: bool = True
    # Sugerencia de mapeo técnico, solo para prellenar el formulario de
    # asociación en frontend2 — no se valida contra datos reales al guardar
    # el cartel (eso ocurre al crear/editar la ASOCIACIÓN, no el cartel).
    fuente_sugerida: AssociationSourceHint | None = None
    variable_tecnica_sugerida: str | None = Field(default=None, max_length=160)
    sensor_modelo_sugerido: str | None = Field(default=None, max_length=160)

    # Metadata visual: posiciona el cartel en la escena del huerto público
    # (frontend/js/catalogo-carteles.js). Opcional porque un cartel sin estos
    # datos simplemente no se dibuja (ver filtro en cargarCatalogoVisual()).
    icono: str | None = Field(default=None, max_length=60)
    grupo_visual: str | None = Field(default=None, max_length=40)
    compartir_conexion_con: str | None = Field(default=None, max_length=100)
    mostrar_conexion: bool = True
    posicion_x: float | None = None
    posicion_y: float | None = None
    destino_x: float | None = None
    destino_y: float | None = None
    destino_zona: str | None = Field(default=None, max_length=160)
    ruta_punto1_x: float | None = None
    ruta_punto1_y: float | None = None
    ruta_punto2_x: float | None = None
    ruta_punto2_y: float | None = None
    ancla: str | None = Field(default=None, max_length=20)
    etiqueta_corta: str | None = Field(default=None, max_length=80)
    explicacion: str | None = Field(default=None, max_length=400)
    regla: dict | None = None
