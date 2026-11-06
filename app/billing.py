"""Cálculo de los conceptos de la factura. Ver docs/FORMULAS.md."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

import psycopg

from app import repository
from app.errors import (
    InconsistentDataError,
    NoDataForPeriodError,
    ServiceNotFoundError,
    TariffNotFoundError,
)
from app.schemas import Period

# Los excedentes tipo 2 son un valor a favor del usuario (CREG 174 de 2021, art. 26).
EE2_SIGN = Decimal(-1)


class Concept(StrEnum):
    EA = "ea"
    EC = "ec"
    EE1 = "ee1"
    EE2 = "ee2"


@dataclass(frozen=True)
class BillingContext:
    service_id: int
    period: Period
    consumption_kwh: Decimal
    injection_kwh: Decimal
    cu: Decimal
    c: Decimal


@dataclass(frozen=True)
class ConceptAmount:
    concept: str
    quantity_kwh: Decimal
    rate: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Invoice:
    consumption_kwh: Decimal
    injection_kwh: Decimal
    concepts: list[ConceptAmount]
    total: Decimal


def _concept_amount(concept: Concept, quantity_kwh: Decimal, rate: Decimal) -> ConceptAmount:
    return ConceptAmount(concept.name, quantity_kwh, rate, quantity_kwh * rate)


def load_context(conn: psycopg.Connection, service_id: int, period: Period) -> BillingContext:
    if not repository.service_exists(conn, service_id):
        raise ServiceNotFoundError(f"No existe el servicio {service_id}")

    totals = repository.fetch_monthly_totals(conn, service_id, period)
    if totals["hours"] == 0:
        raise NoDataForPeriodError(f"El servicio {service_id} no tiene lecturas en el periodo")

    tariff = repository.fetch_tariff(conn, service_id)
    if tariff is None:
        raise TariffNotFoundError(f"No hay tarifa aplicable al servicio {service_id}")

    return BillingContext(
        service_id=service_id,
        period=period,
        consumption_kwh=totals["consumption_kwh"],
        injection_kwh=totals["injection_kwh"],
        cu=tariff["cu"],
        c=tariff["c"],
    )


def calculate_ea(context: BillingContext) -> ConceptAmount:
    return _concept_amount(Concept.EA, context.consumption_kwh, context.cu)


def calculate_ec(context: BillingContext) -> ConceptAmount:
    return _concept_amount(Concept.EC, context.injection_kwh, context.c)


def calculate_ee1(context: BillingContext) -> ConceptAmount:
    quantity_kwh = min(context.injection_kwh, context.consumption_kwh)
    return _concept_amount(Concept.EE1, quantity_kwh, -context.cu)


def calculate_ee2(conn: psycopg.Connection, context: BillingContext) -> ConceptAmount:
    quantity_kwh, value = repository.fetch_hourly_excess_value(
        conn, context.service_id, context.period
    )
    expected_kwh = max(context.injection_kwh - context.consumption_kwh, Decimal(0))
    if quantity_kwh != expected_kwh:
        raise InconsistentDataError(
            f"El exceso horario ({quantity_kwh} kWh) no coincide con el mensual ({expected_kwh} kWh)"
        )

    amount = EE2_SIGN * value
    rate = amount / quantity_kwh if quantity_kwh else Decimal(0)
    return ConceptAmount(Concept.EE2.name, quantity_kwh, rate, amount)


def calculate_concept(
    conn: psycopg.Connection, service_id: int, period: Period, concept: Concept
) -> ConceptAmount:
    context = load_context(conn, service_id, period)
    match concept:
        case Concept.EA:
            return calculate_ea(context)
        case Concept.EC:
            return calculate_ec(context)
        case Concept.EE1:
            return calculate_ee1(context)
        case Concept.EE2:
            return calculate_ee2(conn, context)


def calculate_invoice(conn: psycopg.Connection, service_id: int, period: Period) -> Invoice:
    context = load_context(conn, service_id, period)
    concepts = [
        calculate_ea(context),
        calculate_ec(context),
        calculate_ee1(context),
        calculate_ee2(conn, context),
    ]
    return Invoice(
        consumption_kwh=context.consumption_kwh,
        injection_kwh=context.injection_kwh,
        concepts=concepts,
        total=sum((line.amount for line in concepts), Decimal(0)),
    )
