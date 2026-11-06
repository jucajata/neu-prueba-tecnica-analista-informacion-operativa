from fastapi import Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings


def create_pool() -> ConnectionPool:
    # open=False: el pool se abre en el arranque de la API, sin bloquearla si la
    # base de datos aún no responde. Mientras tanto los endpoints devuelven 503.
    return ConnectionPool(
        settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        timeout=settings.pool_timeout_seconds,
        kwargs={"row_factory": dict_row},
        open=False,
    )


async def get_pool(request: Request) -> ConnectionPool:
    # Los endpoints toman la conexión dentro de su propio hilo. Si lo hiciera una
    # dependencia con yield, FastAPI usaría un segundo hilo para el mismo request y
    # los que esperan una conexión podrían dejar sin hilos a los que ya la tienen.
    return request.app.state.pool
