import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException

from app.db import create_pool
from app.errors import BillingError
from app.routers import analytics, invoices

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.pool = create_pool()
    app.state.pool.open(wait=False)
    yield
    app.state.pool.close()


app = FastAPI(
    title="API de facturación de energía",
    description="Calcula conceptos de factura y estadísticas de consumo e inyección.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(invoices.router)
app.include_router(analytics.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def _error(status_code: int, code: str, detail: str, **extra: object) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "detail": detail, **extra})


@app.exception_handler(BillingError)
def handle_billing_error(_: Request, error: BillingError) -> JSONResponse:
    return _error(error.status_code, error.code, error.detail)


@app.exception_handler(HTTPException)
def handle_http_error(_: Request, error: HTTPException) -> JSONResponse:
    response = _error(error.status_code, HTTPStatus(error.status_code).name, error.detail)
    response.headers.update(error.headers or {})
    return response


@app.exception_handler(RequestValidationError)
def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in error.errors()
    ]
    return _error(422, "VALIDATION_ERROR", "La solicitud no es válida", errors=errors)


@app.exception_handler(psycopg.OperationalError)
@app.exception_handler(PoolTimeout)
def handle_database_unavailable(_: Request, error: Exception) -> JSONResponse:
    logger.error("Base de datos no disponible: %s", error)
    return _error(503, "DATABASE_UNAVAILABLE", "La base de datos no está disponible")


@app.exception_handler(Exception)
def handle_unexpected_error(_: Request, error: Exception) -> JSONResponse:
    logger.exception("Error no controlado", exc_info=error)
    return _error(500, "INTERNAL_ERROR", "Ocurrió un error interno")
