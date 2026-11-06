import math
from decimal import Decimal

import pytest

from tests.conftest import insert_service

SEPTEMBER = "2023-09"
EXAMPLE_HOURS = [("10", "15")] * 10

# EA, EC, EE1, EE2, total, cantidad EE1, cantidad EE2. Calculados aparte desde los CSV.
EXPECTED = {
    3222: (17389790.46, 8131.85, -201458.03, 0.0, 17196464.27, 344.862, 0.0),
    2256: (294241.59, 14243.58, -294241.59, -225869.29, -211625.71, 381.77, 213.2),
    2478: (400620.71, 17425.45, -400620.71, -174350.73, -156925.28, 562.97, 164.91),
}

# -VE según el art. 26 de la CREG 174 de 2021, literal a).
REGULATED_NEGATIVE_VE = {3222: 17196464.27, 2256: -216729.72, 2478: -160873.23}


def invoice(client, service_id, month=SEPTEMBER):
    return client.post("/calculate-invoice", json={"service_id": service_id, "month": month})


def concepts_of(response):
    return {line["concept"]: line for line in response.json()["concepts"]}


@pytest.mark.parametrize("service_id", EXPECTED)
def test_invoice_matches_reference_values(client, service_id):
    ea, ec, ee1, ee2, total, ee1_kwh, ee2_kwh = EXPECTED[service_id]

    response = invoice(client, service_id)

    assert response.status_code == 200
    concepts = concepts_of(response)
    assert concepts["EA"]["amount"] == ea
    assert concepts["EC"]["amount"] == ec
    assert concepts["EE1"]["amount"] == ee1
    assert concepts["EE2"]["amount"] == ee2
    assert concepts["EE1"]["quantity_kwh"] == ee1_kwh
    assert concepts["EE2"]["quantity_kwh"] == ee2_kwh
    assert response.json()["total"] == total


@pytest.mark.parametrize("service_id", EXPECTED)
def test_total_reconciles_with_regulated_value(client, service_id):
    response = invoice(client, service_id)
    concepts = concepts_of(response)
    tariff_c = Decimal(str(concepts["EC"]["rate"]))
    regulated_ec = Decimal(str(concepts["EE1"]["quantity_kwh"])) * tariff_c
    ec_difference = Decimal(str(concepts["EC"]["amount"])) - regulated_ec

    reconciled = Decimal(str(response.json()["total"])) - ec_difference

    assert abs(reconciled - Decimal(str(REGULATED_NEGATIVE_VE[service_id]))) <= Decimal("0.01")


def test_document_example(client, conn):
    insert_service(conn, 901, EXAMPLE_HOURS)

    response = invoice(client, 901, "2000-01")

    concepts = concepts_of(response)
    assert concepts["EA"]["quantity_kwh"] == 100
    assert concepts["EC"]["quantity_kwh"] == 150
    assert concepts["EE1"]["quantity_kwh"] == 100
    assert concepts["EE2"]["quantity_kwh"] == 50
    # Excesos 5, 15, 15 y 15 en las horas 7 a 10, con precios 106, 107, 108 y 109.
    assert concepts["EE2"]["amount"] == -5390
    assert concepts["EE2"]["rate"] == -107.8
    assert concepts["EE1"]["rate"] == -711.62
    assert response.json()["total"] == -1799


def test_excess_is_not_counted_hour_by_hour(client, conn):
    # La hora 1 inyecta más de lo que consume, pero el acumulado nunca supera el consumo total.
    insert_service(conn, 902, [("1", "5"), ("9", "0")])

    concepts = concepts_of(invoice(client, 902, "2000-01"))

    assert concepts["EE1"]["quantity_kwh"] == 5
    assert concepts["EE2"]["quantity_kwh"] == 0
    assert concepts["EE2"]["amount"] == 0


def test_injection_equal_to_consumption_has_no_ee2(client, conn):
    insert_service(conn, 903, [("10", "10"), ("10", "10")])

    concepts = concepts_of(invoice(client, 903, "2000-01"))

    assert concepts["EE1"]["quantity_kwh"] == 20
    assert concepts["EE2"]["quantity_kwh"] == 0
    assert concepts["EE2"]["rate"] == 0


def test_zero_ee2_is_not_negative_zero(client):
    amount = concepts_of(invoice(client, 3222))["EE2"]["amount"]

    assert amount == 0
    assert math.copysign(1, amount) == 1


def test_voltage_level_2_ignores_cdi(client, conn):
    insert_service(conn, 904, [("10", "0")], market=4, cdi=555, voltage_level=2)

    assert concepts_of(invoice(client, 904, "2000-01"))["EA"]["rate"] == 584.17


def test_voltage_level_1_uses_the_tariff_of_its_cdi(client, conn):
    insert_service(conn, 905, [("10", "0")], cdi=50)

    assert concepts_of(invoice(client, 905, "2000-01"))["EA"]["rate"] == 741.18


@pytest.mark.parametrize("concept", ["ea", "ec", "ee1", "ee2"])
@pytest.mark.parametrize("service_id", EXPECTED)
def test_concept_endpoint_matches_invoice(client, service_id, concept):
    line = concepts_of(invoice(client, service_id))[concept.upper()]

    response = client.post(
        f"/calculate-concept/{concept}", json={"service_id": service_id, "month": SEPTEMBER}
    )

    assert response.status_code == 200
    assert response.json() == {"service_id": service_id, "month": SEPTEMBER, **line}
