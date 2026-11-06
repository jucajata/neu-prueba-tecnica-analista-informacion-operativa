# Sistema de facturación de energía

API en FastAPI y PostgreSQL que calcula los conceptos de una factura mensual de energía (EA, EC, EE1 y EE2) y expone estadísticas de consumo e inyección.

Prueba técnica para Erco-Neu.

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) con Docker Compose.
- [uv](https://docs.astral.sh/uv/), solo para ejecutar los tests o la API fuera de Docker.

## Ejecución

```bash
docker compose up -d --build --wait
```

El comando crea el esquema, carga los CSV de `data/` y deja disponible:

- Página con la explicación del proceso, el diagrama entidad-relación y la consola para generar la factura: http://localhost:8000
- Documentación interactiva de la API: http://localhost:8000/docs

Primera consulta:

```bash
curl -X POST http://localhost:8000/calculate-invoice \
  -H 'Content-Type: application/json' \
  -d '{"service_id": 2256, "month": "2023-09"}'
```

Para detener todo y borrar la base de datos:

```bash
docker compose down -v
```

Los servicios de muestra son 2256, 2478 y 3222, con datos de septiembre de 2023.

### Si los puertos están ocupados

```bash
DB_PORT=5433 API_PORT=8001 docker compose up -d --build --wait
```

## Tests

Con la base de datos en ejecución:

```bash
uv sync
uv run pytest
```

Si cambiaste `DB_PORT`, exporta `DATABASE_URL` en la terminal antes de ejecutar los tests; el formato está en `.env.example`. Los tests revierten sus cambios, así que no alteran los datos.

## Ejecutar la API fuera de Docker

```bash
docker compose up -d --wait db
uv run uvicorn app.main:app --reload
```

## Estructura

```
app/
  main.py          aplicación y manejo de errores
  config.py        configuración por variables de entorno
  db.py            pool de conexiones
  schemas.py       modelos de entrada y salida, validación del mes
  errors.py        errores de dominio
  repository.py    consultas SQL
  billing.py       cálculo de los conceptos
  routers/         endpoints
db/
  schema.sql       esquema de la base de datos
  seed.sql         carga de los CSV
data/              datos de muestra
tests/             tests de integración y unitarios
docs/              documentación
```

## Documentación

- [API](docs/API.md): endpoints, ejemplos y errores.
- [Fórmulas](docs/FORMULAS.md): cálculo de cada concepto y sustento regulatorio.
- [Decisiones de diseño](DESIGN.md): decisiones tomadas, supuestos y mejoras futuras.
- [Esquema SQL](db/schema.sql).
