class BillingError(Exception):
    """Error de dominio con su respuesta HTTP asociada."""

    status_code = 500
    code = "BILLING_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ServiceNotFoundError(BillingError):
    status_code = 404
    code = "SERVICE_NOT_FOUND"


class NoDataForPeriodError(BillingError):
    status_code = 404
    code = "NO_DATA_FOR_PERIOD"


class TariffNotFoundError(BillingError):
    status_code = 422
    code = "TARIFF_NOT_FOUND"


class InconsistentDataError(BillingError):
    status_code = 500
    code = "INCONSISTENT_DATA"
