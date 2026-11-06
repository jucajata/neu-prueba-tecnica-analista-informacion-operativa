# Decisiones de diseño

## Arquitectura

Tres capas con responsabilidades separadas:

- `routers/`: HTTP, validación y forma de las respuestas.
- `billing.py`: reglas de negocio de la factura.
- `repository.py`: todo el SQL.

Se usa SQL directo con psycopg, sin ORM, porque la prueba evalúa la optimización de consultas y el cálculo de EE2 depende de funciones de ventana. Los endpoints son síncronos y usan un pool de conexiones: la carga la hace PostgreSQL y FastAPI los ejecuta en su pool de hilos.

Cada endpoint toma la conexión dentro de su propio hilo, no en una dependencia con `yield`. Con la dependencia, cada petición necesitaba un segundo hilo: desde 50 peticiones simultáneas (40 hilos más 10 conexiones), las que esperaban una conexión dejaban sin hilos a las que ya la tenían y la API respondía 503. `tests/test_concurrency.py` cubre este caso con el pool real.

## Página web

`app/static/` contiene una página sin dependencias ni paso de compilación, servida por la misma API en `/`. Explica el cálculo, muestra el diagrama entidad-relación y permite llamar a los cuatro endpoints. El resultado final es la factura de `POST /calculate-invoice`, que se puede imprimir o guardar en PDF. Solo muestra datos que devuelve la API. Los colores y las tipografías (Sora e Inter) siguen el sitio de Erco: azul para lo que se toma de la red y verde para lo que se le entrega.

La API no expone la serie horaria de un servicio, y la curva de la portada la necesita. Se exporta a `app/static/sample.json` con `scripts/export_sample.py`, y `tests/test_frontend.py` comprueba que coincida con la API.

## Interpretación del enunciado

| Punto | Problema | Decisión |
|-------|----------|----------|
| Cantidad de EE2 | El texto dice consumo menos inyección, que sería negativo en ese caso; el ejemplo muestra 150 − 100 = 50 | Inyección menos consumo, como en el ejemplo |
| Exceso de EE2 | Podría leerse como el exceso de cada hora | Se usa la inyección acumulada frente al consumo total del mes, como en el ejemplo. Por hora, el servicio 2256 daría 582,77 kWh en lugar de 213,20 |
| Signo de EE2 | El enunciado no lo define | Negativo, según la CREG 174 de 2021. Ver [fórmulas](docs/FORMULAS.md) |
| Cliente | El modelo no tiene esa entidad | `service_id` identifica al cliente |
| Endpoint por concepto | Admite un endpoint o varios | Uno solo, `POST /calculate-concept/{concept}`, con los conceptos validados por un enum |
| `/system-load` | No se define el detalle | Serie por fecha y hora con consumo sumado, promedio, pico y paginación |
| Tarifas | No tienen fecha | Se asumen vigentes para el periodo cargado |

## Base de datos

- **PK de `tariffs`.** El diagrama marca `id_market`, pero cada mercado tiene 5 tarifas. Se agrega `id_tariff` y una restricción `UNIQUE NULLS NOT DISTINCT` sobre `(id_market, voltage_level, cdi)`, porque `cdi` es NULL en los niveles 2 y 3. Esto exige PostgreSQL 15 o superior.
- **Regla del cdi.** Vive en la vista `service_tariffs`, de modo que ninguna consulta la repite. El servicio 3222 tiene `cdi = 101` y nivel 2, así que un JOIN directo no encontraría tarifa.
- **Relación con `tariffs`.** No se declara FK, porque un servicio de nivel 2 o 3 puede tener cualquier `cdi`. Si falta la tarifa, la API responde `TARIFF_NOT_FOUND`.
- **Tipos.** Se usa `NUMERIC` en lugar del `float` del diagrama, y `Decimal` en Python, para evitar errores de redondeo en dinero. Las columnas están en minúscula para no exigir comillas en cada consulta.
- **Restricciones.** `CHECK` para valores no negativos, nivel de tensión y coherencia del `cdi`; `UNIQUE (id_service, record_timestamp)` para impedir lecturas duplicadas.

## Optimización de consultas

- Los meses se filtran con un rango semiabierto (`>= inicio AND < siguiente`), que aprovecha los índices sobre la fecha y no mezcla años.
- `UNIQUE (id_service, record_timestamp)` también sirve de índice para las consultas por servicio y mes.
- `records (record_timestamp)` sirve a `/system-load`.
- EE2 se resuelve en una sola consulta con CTE y funciones de ventana, sin traer filas a Python.

Medición con `EXPLAIN ANALYZE` sobre datos sintéticos: 200 servicios, 12 meses y 1.752.000 registros, en PostgreSQL 16 sobre Docker local. Es una sola ejecución de cada consulta, así que indica el orden de magnitud:

| Consulta | Sin índices | Con índices |
|----------|-------------|-------------|
| Totales de un servicio en un mes | 63,4 ms | 3,5 ms |
| EE2 de un servicio en un mes | 61,9 ms | 6,6 ms |
| Carga del sistema en un mes (144.000 filas) | 563,8 ms | 320,2 ms |

Filtrar con `to_char(record_timestamp, 'YYYY-MM')` en lugar de un rango tomó 10,0 ms, frente a 3,5 ms: PostgreSQL debe revisar todo el año del servicio (8.760 filas) en lugar de solo el mes (720).

## Manejo de errores

- Todas las respuestas de error tienen la forma `{code, detail}`, documentada en [API](docs/API.md).
- Antes de responder EE2, la cantidad horaria se compara con la mensual. Si no coinciden, se devuelve un error en lugar de una factura incorrecta.
- La API arranca aunque la base de datos no esté disponible: responde 503 y se recupera sola cuando esta vuelve. El pool comprueba cada conexión antes de entregarla, así que una conexión inactiva que murió no llega a una petición.
- La validación ocurre antes de pedir una conexión, así que una solicitud inválida responde 422 aunque la base no esté disponible.

## Pruebas

Los tests de integración usan PostgreSQL real, porque la lógica crítica está en SQL. Cada test corre en una transacción que se revierte. Los valores esperados se calcularon aparte, directamente de los CSV. También se verificó que romper a propósito las reglas críticas (signo de EE2, exceso por hora, orden cronológico, EE1, tarifa de EC, límites del mes y lecturas faltantes) hace fallar la suite.

## Limitaciones

- Las tarifas no tienen vigencia, así que no sirven para más de un periodo tarifario.
- EC sigue el enunciado, que difiere de la regulación cuando la inyección supera al consumo. Ver [conciliación](docs/FORMULAS.md#conciliación-con-la-regulación).
- La regulación distingue por capacidad instalada, un dato que no está en el modelo. Se asume el literal a).
- `/system-load` ejecuta dos consultas sobre todas las filas del periodo: una para el resumen y otra para la página.
- Una hora sin fila en `consumption` o `injection` cuenta como 0 kWh. La API no avisa si faltan lecturas, por lo que una factura con lecturas incompletas no se distingue de una completa.
- La API no tiene autenticación.

## Mejoras futuras

- Agregar `valid_from` y `valid_to` a `tariffs`.
- Reportar en la factura las horas sin lectura.
- Particionar `records` por mes cuando crezca el volumen.
- Usar una vista materializada de carga horaria para `/system-load`.
- Guardar facturas calculadas, para que sean inmutables y auditables.
- Agregar autenticación, migraciones versionadas y métricas.
