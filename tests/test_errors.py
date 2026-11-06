import psycopg
import pytest

from app.db import get_conn
from app.main import app
from tests.conftest import insert_service

VALID_BODY = {"service_id": 2256, "month": "2023-09"}


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert body["code"] == code
    assert body["detail"]


@pytest.mark.parametrize("path", ["/calculate-invoice", "/calculate-concept/ee2"])
def test_unknown_service(client, path):
    response = client.post(path, json={"service_id": 1, "month": "2023-09"})

    assert_error(response, 404, "SERVICE_NOT_FOUND")


@pytest.mark.parametrize("path", ["/calculate-invoice", "/calculate-concept/ea"])
def test_month_without_data(client, path):
    response = client.post(path, json={"service_id": 2256, "month": "2023-10"})

    assert_error(response, 404, "NO_DATA_FOR_PERIOD")


@pytest.mark.parametrize(
    "body",
    [
        {"service_id": 2256, "month": "2023-13"},
        {"service_id": 2256, "month": "septiembre"},
        {"service_id": 0, "month": "2023-09"},
        {"service_id": "x", "month": "2023-09"},
        {"service_id": 2256},
        {"month": "2023-09"},
    ],
)
def test_invalid_body(client, body):
    response = client.post("/calculate-invoice", json=body)

    assert_error(response, 422, "VALIDATION_ERROR")
    assert response.json()["errors"]


def test_unknown_concept(client):
    assert_error(client.post("/calculate-concept/xx", json=VALID_BODY), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize(
    "service",
    [
        {"market": 99},
        {"market": 1, "cdi": 7},
    ],
)
def test_missing_tariff(client, conn, service):
    insert_service(conn, 921, [("1", "0")], **service)

    response = client.post("/calculate-invoice", json={"service_id": 921, "month": "2000-01"})

    assert_error(response, 422, "TARIFF_NOT_FOUND")


def test_statistics_unknown_service(client):
    assert_error(client.get("/client-statistics/1"), 404, "SERVICE_NOT_FOUND")


def test_statistics_month_without_data(client):
    response = client.get("/client-statistics/2256", params={"month": "2023-10"})

    assert_error(response, 404, "NO_DATA_FOR_PERIOD")


def test_statistics_invalid_month(client):
    response = client.get("/client-statistics/2256", params={"month": "2023-13"})

    assert_error(response, 422, "VALIDATION_ERROR")


def test_system_load_month_without_data(client):
    assert_error(client.get("/system-load", params={"month": "2023-10"}), 404, "NO_DATA_FOR_PERIOD")


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 100000}, {"offset": -1}])
def test_system_load_invalid_pagination(client, params):
    assert_error(client.get("/system-load", params=params), 422, "VALIDATION_ERROR")


def test_database_unavailable(client):
    def unavailable():
        raise psycopg.OperationalError("connection refused")

    app.dependency_overrides[get_conn] = unavailable

    assert_error(client.post("/calculate-invoice", json=VALID_BODY), 503, "DATABASE_UNAVAILABLE")
