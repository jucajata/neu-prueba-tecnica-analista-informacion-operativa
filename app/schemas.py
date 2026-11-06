import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, PositiveInt

MONTH_PATTERN = re.compile(r"\d{4}-\d{2}")


@dataclass(frozen=True)
class Period:
    """Rango semiabierto [start, end). Permite usar los índices sobre record_timestamp."""

    start: datetime
    end: datetime


ALL_TIME = Period(datetime.min, datetime.max)


def month_period(value: str) -> Period:
    if not MONTH_PATTERN.fullmatch(value):
        raise ValueError("El mes debe tener el formato YYYY-MM")
    year, month = int(value[:4]), int(value[5:])
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return Period(datetime(year, month, 1), datetime(next_year, next_month, 1))


def _validate_month(value: str) -> str:
    month_period(value)
    return value


def _rounded(decimal_places: int) -> PlainSerializer:
    exponent = Decimal(1).scaleb(-decimal_places)
    return PlainSerializer(
        lambda value: float(value.quantize(exponent, rounding=ROUND_HALF_UP)),
        return_type=float,
    )


Month = Annotated[
    str,
    AfterValidator(_validate_month),
    Field(description="Mes en formato YYYY-MM", examples=["2023-09"]),
]
Money = Annotated[Decimal, _rounded(2)]
Energy = Annotated[Decimal, _rounded(3)]
Rate = Annotated[Decimal, _rounded(4)]


class ErrorResponse(BaseModel):
    code: str = Field(examples=["SERVICE_NOT_FOUND"])
    detail: str = Field(examples=["No existe el servicio 1"])


class InvoiceRequest(BaseModel):
    service_id: PositiveInt = Field(examples=[2256])
    month: Month


class ConceptLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    concept: str = Field(examples=["EE2"])
    quantity_kwh: Energy
    rate: Rate = Field(description="$/kWh. En EE2 es el promedio ponderado de las horas con exceso.")
    amount: Money


class ConceptResponse(ConceptLine):
    service_id: int
    month: str


class InvoiceResponse(BaseModel):
    service_id: int
    month: str
    consumption_kwh: Energy
    injection_kwh: Energy
    concepts: list[ConceptLine]
    total: Money = Field(description="Positivo: paga el usuario. Negativo: saldo a favor del usuario.")


class EnergyStatistics(BaseModel):
    total_kwh: Energy
    average_kwh: Energy
    max_kwh: Energy
    peak_at: datetime


class ClientStatisticsResponse(BaseModel):
    service_id: int
    month: str | None
    hours: int
    consumption: EnergyStatistics
    injection: EnergyStatistics
    net_balance_kwh: Energy = Field(description="Consumo menos inyección")


class HourlyLoad(BaseModel):
    timestamp: datetime
    load_kwh: Energy
    services: int


class PeakLoad(BaseModel):
    timestamp: datetime
    load_kwh: Energy


class SystemLoadResponse(BaseModel):
    month: str | None
    total_hours: int
    average_load_kwh: Energy
    peak: PeakLoad
    limit: int
    offset: int
    items: list[HourlyLoad]
