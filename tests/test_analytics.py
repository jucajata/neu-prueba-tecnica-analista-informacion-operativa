from datetime import datetime

from tests.conftest import insert_service


def iso(csv_timestamp: str) -> str:
    return datetime.fromisoformat(csv_timestamp).isoformat()


def test_client_statistics(client):
    response = client.get("/client-statistics/2256", params={"month": "2023-09"})

    assert response.status_code == 200
    body = response.json()
    assert body["service_id"] == 2256
    assert body["month"] == "2023-09"
    assert body["hours"] == 720
    assert body["consumption"]["total_kwh"] == 381.77
    assert body["consumption"]["average_kwh"] == 0.53
    assert body["injection"]["total_kwh"] == 594.97
    assert body["net_balance_kwh"] == -213.2


def test_client_statistics_without_month_uses_all_data(client):
    body = client.get("/client-statistics/2478").json()

    assert body["month"] is None
    assert body["hours"] == 720
    assert body["consumption"]["total_kwh"] == 562.97


def test_client_statistics_reports_peak_hours(client, conn):
    insert_service(conn, 911, [("1", "9"), ("7", "2"), ("3", "4")])

    body = client.get("/client-statistics/911").json()

    assert body["consumption"]["max_kwh"] == 7
    assert body["consumption"]["peak_at"] == "2000-01-01T01:00:00"
    assert body["injection"]["max_kwh"] == 9
    assert body["injection"]["peak_at"] == "2000-01-01T00:00:00"


def test_system_load_matches_csv(client, csv_load):
    response = client.get("/system-load", params={"month": "2023-09", "limit": 2000})

    assert response.status_code == 200
    body = response.json()
    assert body["total_hours"] == 720
    assert len(body["items"]) == 720
    for item in body["items"][:24]:
        expected = next(v for k, v in csv_load.items() if iso(k) == item["timestamp"])
        assert item["load_kwh"] == float(round(expected, 3))
        assert item["services"] == 3
    peak_key = max(csv_load, key=csv_load.get)
    assert body["peak"]["timestamp"] == iso(peak_key)
    assert body["peak"]["load_kwh"] == float(round(csv_load[peak_key], 3))


def test_system_load_is_paginated_and_ordered(client):
    first = client.get("/system-load", params={"limit": 2}).json()
    second = client.get("/system-load", params={"limit": 2, "offset": 2}).json()

    assert [item["timestamp"] for item in first["items"]] == [
        "2023-09-01T00:00:00",
        "2023-09-01T01:00:00",
    ]
    assert second["items"][0]["timestamp"] == "2023-09-01T02:00:00"
    assert first["total_hours"] == second["total_hours"] == 720
    assert first["peak"] == second["peak"]
