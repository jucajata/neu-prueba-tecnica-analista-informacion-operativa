from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from app import billing
from app.db import get_conn
from app.schemas import ConceptLine, ConceptResponse, ErrorResponse, InvoiceRequest, InvoiceResponse, month_period

router = APIRouter(tags=["Facturación"])

Connection = Annotated[psycopg.Connection, Depends(get_conn)]

ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Servicio inexistente o mes sin lecturas"},
    422: {"model": ErrorResponse, "description": "Solicitud inválida o tarifa inexistente"},
    503: {"model": ErrorResponse, "description": "Base de datos no disponible"},
}


@router.post("/calculate-invoice", response_model=InvoiceResponse, responses=ERROR_RESPONSES)
def calculate_invoice(request: InvoiceRequest, conn: Connection) -> InvoiceResponse:
    """Calcula EA, EC, EE1 y EE2 de un servicio para un mes, y su total."""
    invoice = billing.calculate_invoice(conn, request.service_id, month_period(request.month))
    return InvoiceResponse(
        service_id=request.service_id,
        month=request.month,
        consumption_kwh=invoice.consumption_kwh,
        injection_kwh=invoice.injection_kwh,
        concepts=[ConceptLine.model_validate(line) for line in invoice.concepts],
        total=invoice.total,
    )


@router.post(
    "/calculate-concept/{concept}", response_model=ConceptResponse, responses=ERROR_RESPONSES
)
def calculate_concept(
    concept: billing.Concept, request: InvoiceRequest, conn: Connection
) -> ConceptResponse:
    """Calcula un solo concepto de la factura de un servicio para un mes."""
    line = billing.calculate_concept(
        conn, request.service_id, month_period(request.month), concept
    )
    return ConceptResponse(
        service_id=request.service_id,
        month=request.month,
        concept=line.concept,
        quantity_kwh=line.quantity_kwh,
        rate=line.rate,
        amount=line.amount,
    )
