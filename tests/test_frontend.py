import json
import re
from pathlib import Path

import pytest

from app import main

STATIC_DIR = Path(main.__file__).parent / "static"
SERVICES = ["2256", "2478", "3222"]


def sample() -> dict:
    return json.loads((STATIC_DIR / "sample.json").read_text(encoding="utf-8"))


def test_home_serves_the_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_page_assets_are_served(client):
    assets = re.findall(r'(?:src|href)="(/static/[^"]+)"', client.get("/").text)

    assert assets
    for asset in assets:
        assert client.get(asset).status_code == 200, asset


def test_page_is_not_part_of_the_api_contract(client):
    assert "/" not in client.get("/openapi.json").json()["paths"]


def test_page_only_calls_documented_endpoints(client):
    paths = re.findall(r'path: "([^"]+)"', (STATIC_DIR / "app.js").read_text(encoding="utf-8"))

    assert sorted(paths) == sorted(client.get("/openapi.json").json()["paths"])


@pytest.mark.parametrize("service_id", SERVICES)
def test_sample_invoice_matches_the_api(client, service_id):
    response = client.post(
        "/calculate-invoice", json={"service_id": int(service_id), "month": "2023-09"}
    )

    assert sample()["services"][service_id]["invoice"] == response.json()


@pytest.mark.parametrize("service_id", SERVICES)
def test_sample_curve_ends_at_the_monthly_injection(service_id):
    service = sample()["services"][service_id]

    assert len(service["accumulated_kwh"]) == 720
    assert service["accumulated_kwh"][-1] == service["invoice"]["injection_kwh"]
