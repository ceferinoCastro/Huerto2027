from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


CampaignState = Literal["planificada", "activa", "finalizada", "cancelada"]


def _meaningful(value: str | None, label: str) -> str:
    text = (value or "").strip()
    if len(text) < 3:
        raise ValueError(f"{label} debe contener al menos 3 caracteres")
    return text


class StrictCampaignModel(BaseModel):
    model_config = {"extra": "forbid"}


class CampaignCreateInput(StrictCampaignModel):
    colegio_id: str = Field(min_length=1)
    cultivo: str = Field(min_length=1, max_length=120)
    fecha_siembra: date
    fecha_cosecha_estimada: date
    observaciones: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.fecha_cosecha_estimada < self.fecha_siembra:
            raise ValueError("La cosecha estimada no puede ser anterior a la siembra")
        self.cultivo = self.cultivo.strip()
        self.observaciones = self.observaciones.strip()
        return self


class CampaignEditInput(StrictCampaignModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    cultivo: str | None = Field(default=None, min_length=1, max_length=120)
    fecha_siembra: date | None = None
    fecha_cosecha_estimada: date | None = None
    observaciones: str | None = Field(default=None, max_length=2000)
    fecha_cosecha_real: date | None = None
    resultado_final: str | None = Field(default=None, max_length=3000)
    observaciones_finales: str | None = Field(default=None, max_length=3000)
    fecha_cancelacion: date | None = None
    motivo_cancelacion: str | None = Field(default=None, max_length=2000)
    motivo_correccion: str | None = Field(default=None, max_length=1000)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_update(self):
        editable = self.model_fields_set - {"revision", "motivo_correccion"}
        if not editable:
            raise ValueError("Debe modificar al menos un campo de la campaña")
        for field in editable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser nulo")
        if self.nombre is not None:
            self.nombre = self.nombre.strip()
        if self.cultivo is not None:
            self.cultivo = self.cultivo.strip()
        if self.motivo_correccion is not None:
            self.motivo_correccion = _meaningful(
                self.motivo_correccion, "El motivo de la corrección"
            )
        return self


class CampaignFinishInput(StrictCampaignModel):
    fecha_cosecha_real: date
    resultado_final: str = Field(min_length=3, max_length=3000)
    observaciones_finales: str = Field(default="", max_length=3000)
    confirmar: bool
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_finish(self):
        if not self.confirmar:
            raise ValueError("Debe confirmar explícitamente la finalización")
        self.resultado_final = _meaningful(self.resultado_final, "El resultado final")
        self.observaciones_finales = self.observaciones_finales.strip()
        return self


class CampaignCancelInput(StrictCampaignModel):
    fecha_cancelacion: date
    motivo_cancelacion: str = Field(min_length=3, max_length=2000)
    categoria_motivo: Literal[
        "Error de registro",
        "Campaña duplicada",
        "Cultivo perdido",
        "Cambio de planificación",
        "Otro",
    ]
    confirmar: bool
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_cancel(self):
        if not self.confirmar:
            raise ValueError("Debe confirmar explícitamente la cancelación")
        self.motivo_cancelacion = _meaningful(
            self.motivo_cancelacion, "El motivo de cancelación"
        )
        if self.categoria_motivo == "Otro" and len(self.motivo_cancelacion) < 5:
            raise ValueError("Explique el motivo de cancelación")
        return self


class CampaignReopenInput(StrictCampaignModel):
    motivo: str = Field(min_length=3, max_length=1000)
    confirmar: bool
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_reopen(self):
        if not self.confirmar:
            raise ValueError("Debe confirmar explícitamente la reapertura")
        self.motivo = _meaningful(self.motivo, "El motivo de reapertura")
        return self


class CampaignResponse(BaseModel):
    id: str = Field(alias="_id")
    colegio_id: str
    nombre: str
    cultivo: str
    fecha_siembra: str | None
    fecha_cosecha_estimada: str | None
    fecha_cosecha_real: str | None = None
    fecha_cancelacion: str | None = None
    estado: CampaignState
    observaciones: str = ""
    resultado_final: str = ""
    observaciones_finales: str = ""
    motivo_cancelacion: str = ""
    categoria_motivo: str | None = None
    historial_cambios: list[dict] = Field(default_factory=list)
    revision: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"populate_by_name": True}
