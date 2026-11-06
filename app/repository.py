"""Consultas SQL. Los meses se filtran por rango para aprovechar los índices."""

from decimal import Decimal
from typing import Any

import psycopg

from app.schemas import Period

Row = dict[str, Any]

_SERVICE_RECORDS = """
    FROM records r
    LEFT JOIN consumption c ON c.id_record = r.id_record
    LEFT JOIN injection i ON i.id_record = r.id_record
    WHERE r.id_service = %(service_id)s
      AND r.record_timestamp >= %(start)s
      AND r.record_timestamp < %(end)s
"""

_MONTHLY_TOTALS = f"""
    SELECT COUNT(*) AS hours,
           COALESCE(SUM(c.value), 0) AS consumption_kwh,
           COALESCE(SUM(i.value), 0) AS injection_kwh
    {_SERVICE_RECORDS}
"""

# Exceso de cada hora respecto al consumo total del mes, sobre la inyección
# acumulada. Es Exc2 del art. 26 de la CREG 174 de 2021: en la hora hx vale el
# acumulado menos el consumo total, y después, toda la inyección de la hora.
_HOURLY_EXCESS_VALUE = f"""
    WITH hourly AS (
        SELECT r.record_timestamp,
               COALESCE(i.value, 0) AS injection_kwh,
               SUM(COALESCE(i.value, 0)) OVER (ORDER BY r.record_timestamp) AS accumulated_kwh,
               SUM(COALESCE(c.value, 0)) OVER () AS imported_kwh
        {_SERVICE_RECORDS}
    ),
    excess AS (
        SELECT record_timestamp,
               LEAST(injection_kwh, GREATEST(accumulated_kwh - imported_kwh, 0)) AS excess_kwh
        FROM hourly
    )
    SELECT COALESCE(SUM(e.excess_kwh), 0) AS quantity_kwh,
           COALESCE(SUM(e.excess_kwh * x.value), 0) AS value
    FROM excess e
    JOIN xm_data_hourly_per_agent x ON x.record_timestamp = e.record_timestamp
    WHERE e.excess_kwh > 0
"""

_SERVICE_STATISTICS = f"""
    SELECT COUNT(*) AS hours,
           COALESCE(SUM(c.value), 0) AS consumption_total,
           COALESCE(AVG(c.value), 0) AS consumption_average,
           COALESCE(MAX(c.value), 0) AS consumption_max,
           (ARRAY_AGG(r.record_timestamp ORDER BY c.value DESC NULLS LAST, r.record_timestamp))[1]
               AS consumption_peak_at,
           COALESCE(SUM(i.value), 0) AS injection_total,
           COALESCE(AVG(i.value), 0) AS injection_average,
           COALESCE(MAX(i.value), 0) AS injection_max,
           (ARRAY_AGG(r.record_timestamp ORDER BY i.value DESC NULLS LAST, r.record_timestamp))[1]
               AS injection_peak_at
    {_SERVICE_RECORDS}
"""

_HOURLY_LOAD = """
    SELECT r.record_timestamp AS timestamp,
           SUM(c.value) AS load_kwh,
           COUNT(*) AS services
    FROM records r
    JOIN consumption c ON c.id_record = r.id_record
    WHERE r.record_timestamp >= %(start)s
      AND r.record_timestamp < %(end)s
    GROUP BY r.record_timestamp
"""

_SYSTEM_LOAD_SUMMARY = f"""
    WITH hourly AS ({_HOURLY_LOAD})
    SELECT COUNT(*) AS total_hours,
           AVG(load_kwh) AS average_load_kwh,
           MAX(load_kwh) AS peak_load_kwh,
           (ARRAY_AGG(timestamp ORDER BY load_kwh DESC, timestamp))[1] AS peak_at
    FROM hourly
"""


def _service_params(service_id: int, period: Period) -> Row:
    return {"service_id": service_id, "start": period.start, "end": period.end}


def service_exists(conn: psycopg.Connection, service_id: int) -> bool:
    query = "SELECT 1 FROM services WHERE id_service = %s"
    return conn.execute(query, (service_id,)).fetchone() is not None


def fetch_tariff(conn: psycopg.Connection, service_id: int) -> Row | None:
    query = "SELECT cu, c FROM service_tariffs WHERE id_service = %s"
    return conn.execute(query, (service_id,)).fetchone()


def fetch_monthly_totals(conn: psycopg.Connection, service_id: int, period: Period) -> Row:
    return conn.execute(_MONTHLY_TOTALS, _service_params(service_id, period)).fetchone()


def fetch_hourly_excess_value(
    conn: psycopg.Connection, service_id: int, period: Period
) -> tuple[Decimal, Decimal]:
    """Devuelve la cantidad en kWh y el valor en $ de los excedentes tipo 2."""
    row = conn.execute(_HOURLY_EXCESS_VALUE, _service_params(service_id, period)).fetchone()
    return row["quantity_kwh"], row["value"]


def fetch_service_statistics(conn: psycopg.Connection, service_id: int, period: Period) -> Row:
    return conn.execute(_SERVICE_STATISTICS, _service_params(service_id, period)).fetchone()


def fetch_system_load_summary(conn: psycopg.Connection, period: Period) -> Row:
    params = {"start": period.start, "end": period.end}
    return conn.execute(_SYSTEM_LOAD_SUMMARY, params).fetchone()


def fetch_system_load(
    conn: psycopg.Connection, period: Period, limit: int, offset: int
) -> list[Row]:
    query = f"{_HOURLY_LOAD} ORDER BY r.record_timestamp LIMIT %(limit)s OFFSET %(offset)s"
    params = {"start": period.start, "end": period.end, "limit": limit, "offset": offset}
    return conn.execute(query, params).fetchall()
