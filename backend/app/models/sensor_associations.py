from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.compatibility import LOCALITIES


AssociationSource = Literal["zentra", "hanna", "manual"]


class SensorAssociationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    localidad: str
    colegio_id: str = Field(min_length=1)
    device_sn: str | None = None
    clave_educativa: str = Field(min_length=1, max_length=100)
    sensor_sn: str | None = None
    sensor_name: str | None = Field(default=None, max_length=160)
    variable_tecnica: str = Field(min_length=1, max_length=160)
    ubicacion: str | None = Field(default=None, max_length=240)
    profundidad_cm: float | None = Field(default=None, ge=0, le=1000)
    source: AssociationSource = "zentra"

    @field_validator("localidad")
    @classmethod
    def validate_locality(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in LOCALITIES:
            raise ValueError("Localidad no soportada")
        return normalized

    @field_validator("device_sn", "sensor_sn", "sensor_name", "ubicacion")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_source_identifiers(self):
        if self.source == "zentra" and (not self.device_sn or not self.sensor_sn):
            raise ValueError("Una asociación Zentra requiere device_sn y sensor_sn")
        if self.source == "manual" and self.clave_educativa not in {
            "altura_planta",
            "largo_raiz",
        }:
            raise ValueError("Variable manual no soportada")
        return self
