from datetime import date

from pydantic import BaseModel, Field, field_validator


class PlantMeasurementInput(BaseModel):
    planta_numero: int = Field(ge=1)
    altura_cm: float = Field(gt=0)


class PlantMeasurementItem(BaseModel):
    planta_numero: int
    altura_cm: float
    observacion: str = ""


class DailyPlantMeasurementsInput(BaseModel):
    localidad: str = Field(min_length=1)
    fecha: date
    mediciones: list[PlantMeasurementInput] = Field(min_length=1)
    observacion: str | None = Field(default=None, max_length=1000)
    colegio_id: str | None = None
    huerto_id: str | None = None
    ciclo_id: str = Field(default="general", min_length=1)

    @field_validator("mediciones")
    @classmethod
    def unique_plant_numbers(
        cls,
        measurements: list[PlantMeasurementInput],
    ) -> list[PlantMeasurementInput]:
        plant_numbers = [item.planta_numero for item in measurements]
        if len(plant_numbers) != len(set(plant_numbers)):
            raise ValueError("planta_numero no puede repetirse")
        return measurements


class DailyPlantAverage(BaseModel):
    fecha: date
    altura_promedio_cm: float
    plantas_medidas: int


class DailyPlantAveragesResponse(BaseModel):
    localidad: str
    count: int
    items: list[DailyPlantAverage]


class DailyPlantMeasurementsResponse(BaseModel):
    status: str = "ok"
    localidad: str
    fecha: date
    ciclo_id: str
    count: int
    items: list[PlantMeasurementItem]
