from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HannaAssociateInput(BaseModel):
    serial_hanna: str = Field(min_length=3, max_length=80)
    modelo: str = Field(default="HI981420", min_length=1, max_length=80)
    instrument_id: str = Field(default="", max_length=80)
    colegio_id: str = Field(min_length=1)
    fecha_asignacion: date = Field(default_factory=date.today)

    @field_validator("serial_hanna")
    @classmethod
    def normalize_serial(cls, value: str) -> str:
        return value.strip().upper()


class HannaCorrectionInput(BaseModel):
    colegio_id: str = Field(min_length=1)
    confirmar: bool
    usuario: str | None = Field(default=None, max_length=200)

    @field_validator("confirmar")
    @classmethod
    def require_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Debe confirmar explícitamente la corrección")
        return value


class HannaReplacementInput(BaseModel):
    serial_hanna_nuevo: str = Field(min_length=3, max_length=80)
    modelo: str = Field(default="HI981420", min_length=1, max_length=80)
    instrument_id: str = Field(default="", max_length=80)
    fecha_asignacion: date = Field(default_factory=date.today)

    @field_validator("serial_hanna_nuevo")
    @classmethod
    def normalize_serial(cls, value: str) -> str:
        return value.strip().upper()


class HannaDataloggerResponse(BaseModel):
    serial_hanna: str
    modelo: str
    instrument_id: str
    colegio_id: str
    colegio_nombre: str
    localidad: str | None = None
    estado: Literal["activo", "reemplazado"]
    fecha_asignacion: str
    fecha_baja: str | None = None
    reemplazado_por: str | None = None
    created_at: datetime
    updated_at: datetime

