from typing import Annotated

from fastapi import APIRouter, Depends, Query
from psycopg_pool import ConnectionPool

from app import repository
from app.db import get_pool
from app.errors import NoDataForPeriodError, ServiceNotFoundError
from app.schemas import (
    ALL_TIME,
    ClientStatisticsResponse,
    EnergyStatistics,
    ErrorResponse,
    HourlyLoad,
    Month,
    PeakLoad,
    Period,
    SystemLoadResponse,
    month_period,
)

router = APIRouter(tags=["Análisis"])

Pool = Annotated[ConnectionPool, Depends(get_pool)]
OptionalMonth = Annotated[Month | None, Query(description="Mes YYYY-MM. Sin él, usa todos los datos.")]

MAX_OFFSET = 2_147_483_647

ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Servicio inexistente o periodo sin lecturas"},
    422: {"model": ErrorResponse, "description": "Parámetros inválidos"},
    503: {"model": ErrorResponse, "description": "Base de datos no disponible"},
}


def _period(month: str | None) -> Period:
    return month_period(month) if month else ALL_TIME


def _energy_statistics(row: repository.Row, prefix: str) -> EnergyStatistics:
    max_kwh = row[f"{prefix}_max"]
    return EnergyStatistics(
        total_kwh=row[f"{prefix}_total"],
        average_kwh=row[f"{prefix}_average"],
        max_kwh=max_kwh,
        peak_at=row[f"{prefix}_peak_at"] if max_kwh > 0 else None,
    )


@router.get(
    "/client-statistics/{service_id}",
    response_model=ClientStatisticsResponse,
    responses=ERROR_RESPONSES,
)
def client_statistics(
    service_id: int, pool: Pool, month: OptionalMonth = None
) -> ClientStatisticsResponse:
    """Estadísticas de consumo e inyección de un servicio."""
    with pool.connection() as conn:
        if not repository.service_exists(conn, service_id):
            raise ServiceNotFoundError(f"No existe el servicio {service_id}")
        row = repository.fetch_service_statistics(conn, service_id, _period(month))

    if row["hours"] == 0:
        raise NoDataForPeriodError(f"El servicio {service_id} no tiene lecturas en el periodo")

    return ClientStatisticsResponse(
        service_id=service_id,
        month=month,
        hours=row["hours"],
        consumption=_energy_statistics(row, "consumption"),
        injection=_energy_statistics(row, "injection"),
        net_balance_kwh=row["consumption_total"] - row["injection_total"],
    )


@router.get("/system-load", response_model=SystemLoadResponse, responses=ERROR_RESPONSES)
def system_load(
    pool: Pool,
    month: OptionalMonth = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> SystemLoadResponse:
    """Carga del sistema por hora: consumo sumado de todos los servicios."""
    period = _period(month)
    with pool.connection() as conn:
        summary = repository.fetch_system_load_summary(conn, period)
        if summary["total_hours"] == 0:
            raise NoDataForPeriodError("No hay lecturas en el periodo")
        rows = repository.fetch_system_load(conn, period, limit, offset)

    return SystemLoadResponse(
        month=month,
        total_hours=summary["total_hours"],
        average_load_kwh=summary["average_load_kwh"],
        peak=PeakLoad(timestamp=summary["peak_at"], load_kwh=summary["peak_load_kwh"]),
        limit=limit,
        offset=offset,
        items=[HourlyLoad(**row) for row in rows],
    )
