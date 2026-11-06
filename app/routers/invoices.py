from typing import Annotated

from fastapi import APIRouter, Depends
from psycopg_pool import ConnectionPool

from app import billing
from app.db import get_pool
from app.schemas import ConceptLine, ConceptResponse, ErrorResponse, InvoiceRequest, InvoiceResponse, month_period

router = APIRouter(tags=["Facturación"])

Pool = Annotated[ConnectionPool, Depends(get_pool)]

ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Servicio inexistente o mes sin lecturas"},
    422: {"model": ErrorResponse, "description": "Solicitud inválida o tarifa inexistente"},
    503: {"model": ErrorResponse, "description": "Base de datos no disponible"},
}


@router.post("/calculate-invoice", response_model=InvoiceResponse, responses=ERROR_RESPONSES)
def calculate_invoice(request: InvoiceRequest, pool: Pool) -> InvoiceResponse:
    """Calcula EA, EC, EE1 y EE2 de un servicio para un mes, y su total."""
    with pool.connection() as conn:
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
    concept: billing.Concept, request: InvoiceRequest, pool: Pool
) -> ConceptResponse:
    """Calcula un solo concepto de la factura de un servicio para un mes."""
    with pool.connection() as conn:
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
