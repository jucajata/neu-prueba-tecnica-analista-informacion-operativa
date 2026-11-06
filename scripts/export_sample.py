"""Genera app/static/sample.json con la curva y la factura que muestra la página.

La API no expone la serie horaria de un servicio, así que se exporta una sola vez a
partir de los datos de muestra. tests/test_frontend.py la compara con la API.

Uso: uv run python -m scripts.export_sample
"""

import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app import billing
from app.config import settings
from app.schemas import ConceptLine, InvoiceResponse, month_period

MONTH = "2023-09"
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "static" / "sample.json"

ACCUMULATED_INJECTION = """
    SELECT r.record_timestamp,
           SUM(COALESCE(i.value, 0)) OVER (ORDER BY r.record_timestamp) AS accumulated_kwh
    FROM records r
    LEFT JOIN injection i ON i.id_record = r.id_record
    WHERE r.id_service = %s AND r.record_timestamp >= %s AND r.record_timestamp < %s
    ORDER BY r.record_timestamp
"""


def export_service(conn: psycopg.Connection, service: dict) -> dict:
    period = month_period(MONTH)
    invoice = billing.calculate_invoice(conn, service["id_service"], period)
    rows = conn.execute(
        ACCUMULATED_INJECTION, (service["id_service"], period.start, period.end)
    ).fetchall()
    crossing = next(
        (i for i, row in enumerate(rows) if row["accumulated_kwh"] >= invoice.consumption_kwh),
        None,
    )
    response = InvoiceResponse(
        service_id=service["id_service"],
        month=MONTH,
        consumption_kwh=invoice.consumption_kwh,
        injection_kwh=invoice.injection_kwh,
        concepts=[ConceptLine.model_validate(line) for line in invoice.concepts],
        total=invoice.total,
    )
    return {
        "market": service["id_market"],
        "voltage_level": service["voltage_level"],
        "cdi": service["cdi"],
        "start": rows[0]["record_timestamp"].isoformat(),
        "crossing_hour": crossing,
        "accumulated_kwh": [round(float(row["accumulated_kwh"]), 3) for row in rows],
        "invoice": response.model_dump(mode="json"),
    }


def main() -> None:
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        services = conn.execute("SELECT * FROM services ORDER BY id_service").fetchall()
        sample = {
            "month": MONTH,
            "services": {str(s["id_service"]): export_service(conn, s) for s in services},
        }
    OUTPUT.write_text(json.dumps(sample, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
