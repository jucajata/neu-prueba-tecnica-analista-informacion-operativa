import csv
import os
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.db import get_pool
from app.main import app

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://billing:billing@localhost:5432/billing")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    """Conexión cuyo contenido se revierte al final de cada test."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        yield connection
        connection.rollback()


class SingleConnectionPool:
    """Entrega siempre la conexión del test, para que sus cambios se puedan revertir."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        yield self._connection


@pytest.fixture
def client(conn: psycopg.Connection) -> Iterator[TestClient]:
    app.dependency_overrides[get_pool] = lambda: SingleConnectionPool(conn)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def real_pool_client() -> Iterator[TestClient]:
    """Cliente que usa el pool de conexiones real de la aplicación."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def insert_service(
    conn: psycopg.Connection,
    service_id: int,
    hourly: list[tuple[str | None, str | None]],
    *,
    market: int = 1,
    cdi: int = 0,
    voltage_level: int = 1,
    first_hour: datetime = datetime(2000, 1, 1),
    descending_ids: bool = False,
) -> None:
    """Crea un servicio con lecturas (consumo, inyección) y precio XM de 100 + hora.

    None omite la fila de esa lectura. descending_ids hace que el id no siga el orden
    cronológico, para comprobar que los cálculos no dependen de él.
    """
    conn.execute(
        "INSERT INTO services (id_service, id_market, cdi, voltage_level) VALUES (%s, %s, %s, %s)",
        (service_id, market, cdi, voltage_level),
    )
    for hour, (consumption, injection) in enumerate(hourly):
        timestamp = first_hour + timedelta(hours=hour)
        record_id = service_id * 1000 + (len(hourly) - hour if descending_ids else hour)
        conn.execute(
            """
            INSERT INTO xm_data_hourly_per_agent (record_timestamp, value)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
            """,
            (timestamp, 100 + hour),
        )
        conn.execute(
            "INSERT INTO records (id_record, id_service, record_timestamp) VALUES (%s, %s, %s)",
            (record_id, service_id, timestamp),
        )
        if consumption is not None:
            conn.execute("INSERT INTO consumption VALUES (%s, %s)", (record_id, consumption))
        if injection is not None:
            conn.execute("INSERT INTO injection VALUES (%s, %s)", (record_id, injection))


@pytest.fixture(scope="session")
def csv_load() -> dict[str, Decimal]:
    """Carga por hora calculada directamente de los CSV, sin pasar por la API."""
    with (DATA_DIR / "records.csv").open(newline="") as file:
        hour_by_record = {row["id_record"]: row["record_timestamp"] for row in csv.DictReader(file)}
    load: dict[str, Decimal] = defaultdict(Decimal)
    with (DATA_DIR / "consumption.csv").open(newline="") as file:
        for row in csv.DictReader(file):
            load[hour_by_record[row["id_record"]]] += Decimal(row["value"])
    return dict(load)
