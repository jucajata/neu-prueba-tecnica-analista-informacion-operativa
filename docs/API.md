# Documentación de la API

La documentación interactiva está en `http://localhost:8000/docs`, con la especificación en `/openapi.json`.

Convenciones:

- `month` usa el formato `YYYY-MM`.
- `service_id` identifica al cliente, ya que el modelo no tiene una entidad cliente.
- Las respuestas redondean los valores en $ a 2 decimales, los kWh a 3 y las tarifas a 4.
- El total se calcula con precisión completa y se redondea una sola vez, por lo que puede diferir en $0,01 de la suma de las líneas redondeadas.
- En `amount` y `total`, un valor positivo lo paga el usuario y uno negativo está a su favor.

## POST /calculate-invoice

Calcula EA, EC, EE1 y EE2 de un servicio para un mes.

```bash
curl -X POST http://localhost:8000/calculate-invoice \
  -H 'Content-Type: application/json' \
  -d '{"service_id": 2256, "month": "2023-09"}'
```

Respuesta `200`:

```json
{
  "service_id": 2256,
  "month": "2023-09",
  "consumption_kwh": 381.77,
  "injection_kwh": 594.97,
  "concepts": [
    {"concept": "EA", "quantity_kwh": 381.77, "rate": 770.73, "amount": 294241.59},
    {"concept": "EC", "quantity_kwh": 594.97, "rate": 23.94, "amount": 14243.58},
    {"concept": "EE1", "quantity_kwh": 381.77, "rate": -770.73, "amount": -294241.59},
    {"concept": "EE2", "quantity_kwh": 213.2, "rate": -1059.4245, "amount": -225869.29}
  ],
  "total": -211625.71
}
```

En EE2, `rate` es el promedio ponderado de los precios horarios. El valor real se calcula hora a hora.

## POST /calculate-concept/{concept}

Calcula un solo concepto. `concept` puede ser `ea`, `ec`, `ee1` o `ee2`, y el cuerpo es el mismo de `/calculate-invoice`.

```bash
curl -X POST http://localhost:8000/calculate-concept/ee2 \
  -H 'Content-Type: application/json' \
  -d '{"service_id": 2256, "month": "2023-09"}'
```

Respuesta `200`:

```json
{
  "concept": "EE2",
  "quantity_kwh": 213.2,
  "rate": -1059.4245,
  "amount": -225869.29,
  "service_id": 2256,
  "month": "2023-09"
}
```

## GET /client-statistics/{service_id}

Devuelve estadísticas de consumo e inyección de un servicio. `month` es opcional; sin él, se usan todos los datos. `peak_at` es la hora del valor máximo, o `null` si el máximo es 0.

```bash
curl 'http://localhost:8000/client-statistics/2256?month=2023-09'
```

Respuesta `200`:

```json
{
  "service_id": 2256,
  "month": "2023-09",
  "hours": 720,
  "consumption": {"total_kwh": 381.77, "average_kwh": 0.53, "max_kwh": 3.81, "peak_at": "2023-09-12T20:00:00"},
  "injection": {"total_kwh": 594.97, "average_kwh": 0.826, "max_kwh": 4.37, "peak_at": "2023-09-23T13:00:00"},
  "net_balance_kwh": -213.2
}
```

`net_balance_kwh` es el consumo menos la inyección.

## GET /system-load

Devuelve la carga por hora: el consumo sumado de todos los servicios.

| Parámetro | Por defecto | Descripción |
|-----------|-------------|-------------|
| `month` | Todos los datos | Mes a consultar |
| `limit` | 1000 | Horas por página, entre 1 y 5000 |
| `offset` | 0 | Horas a omitir, hasta 2147483647 |

`total_hours`, `average_load_kwh` y `peak` describen todo el periodo, no solo la página.

```bash
curl 'http://localhost:8000/system-load?month=2023-09&limit=2'
```

Respuesta `200`:

```json
{
  "month": "2023-09",
  "total_hours": 720,
  "average_load_kwh": 42.657,
  "peak": {"timestamp": "2023-09-12T16:00:00", "load_kwh": 77.912},
  "limit": 2,
  "offset": 0,
  "items": [
    {"timestamp": "2023-09-01T00:00:00", "load_kwh": 55.725, "services": 3},
    {"timestamp": "2023-09-01T01:00:00", "load_kwh": 63.96, "services": 3}
  ]
}
```

## Errores

Todos los errores tienen la misma forma:

```json
{"code": "SERVICE_NOT_FOUND", "detail": "No existe el servicio 1"}
```

| Estado | `code` | Causa |
|--------|--------|-------|
| 404 | `SERVICE_NOT_FOUND` | El servicio no existe |
| 404 | `NO_DATA_FOR_PERIOD` | No hay lecturas en el periodo |
| 404 | `NOT_FOUND` | La ruta no existe |
| 405 | `METHOD_NOT_ALLOWED` | La ruta no admite ese método |
| 422 | `VALIDATION_ERROR` | Parámetros o cuerpo inválidos; incluye `errors` con el campo y el mensaje |
| 422 | `TARIFF_NOT_FOUND` | Ninguna tarifa corresponde al mercado, nivel y cdi del servicio |
| 500 | `INCONSISTENT_DATA` | El exceso horario no coincide con el mensual |
| 500 | `INTERNAL_ERROR` | Error no controlado |
| 503 | `DATABASE_UNAVAILABLE` | La base de datos no responde |
