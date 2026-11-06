# Fórmulas de liquidación

Este documento relaciona los cuatro conceptos de la factura con la regulación colombiana de autogeneración a pequeña escala (AGPE) y justifica el signo de EE2, que el enunciado de la prueba no define.

**Fuente:** [Resolución CREG 174 de 2021](https://normas.cra.gov.co/gestor/docs/resolucion_creg_0174_2021.htm), artículos 25 y 26, en el texto original vigente en septiembre de 2023, el periodo de los datos.

## Fórmulas implementadas

Con $C$ como suma mensual de `consumption.value` e $I$ como suma mensual de `injection.value`:

| Concepto | Cantidad (kWh) | Tarifa ($/kWh) | Valor |
|----------|----------------|----------------|-------|
| EA | $C$ | $CU$ | $C \cdot CU$ |
| EC | $I$ | $C_{tarifa}$ (columna `c` de `tariffs`) | $I \cdot C_{tarifa}$ |
| EE1 | $\min(I, C)$ | $-CU$ | $-\min(I, C) \cdot CU$ |
| EE2 | $\max(I - C, 0)$ | $-Pbolsa_h$ en cada hora | $-\sum_h q_h \cdot Pbolsa_h$ |

El total de la factura es $EA + EC + EE1 + EE2$. Si es positivo, paga el usuario; si es negativo, es saldo a su favor.

### Cantidad horaria de EE2

$q_h$ se calcula sobre la inyección acumulada del mes, no sobre el exceso de cada hora. Con $A_h$ como inyección acumulada hasta la hora $h$:

$$q_h = \min\left(inyeccion_h,\ \max(A_h - C,\ 0)\right)$$

Esta es la implementación en SQL, en `app/repository.py`:

```sql
LEAST(injection_kwh, GREATEST(accumulated_kwh - imported_kwh, 0))
```

Con el ejemplo del enunciado ($C = 100$ e inyección de 15 kWh por hora), el acumulado llega a 105 en la hora 7:

| Hora | 1 a 6 | 7 | 8 | 9 | 10 | Suma |
|------|-------|---|---|---|----|------|
| $A_h$ | 15 a 90 | 105 | 120 | 135 | 150 | |
| $q_h$ | 0 | 5 | 15 | 15 | 15 | 50 |

## Fórmulas de la regulación

El artículo 26 define la valoración del excedente, $VE$. El texto de la prueba corresponde a un AGPE que aplica crédito de energía.

**Literal a), capacidad instalada o nominal menor o igual a 100 kW:**

$$VE_{i,j,n,m,u} = (Exc1_{i,j,m,u} - Imp_{i,j,m,u}) * CUv_{n,m,i,j} - [Exc1_{i,j,m,u} * Cv_{m,i,j}] + \sum_{h=hx,hx+1,...,H} Exc2_{i,j,m,h,u} * Pbolsa_{h,m}$$

**Literal b), capacidad mayor a 100 kW y menor o igual a 1.000 kW:**

$$VE_{i,j,n,m,u} = (Exc1_{i,j,m,u} - Imp_{i,j,m,u}) * CUv_{n,m,i,j} - [Exc1_{i,j,m,u} * Cv_{m,i,j}] - [Exc1_{i,j,m,u} * (T_m + D_{n,m} + PR_{n,m,i,j} + R_{m,i})] + \sum_{h=hx,hx+1,...,H} Exc2_{i,j,m,h,u} * Pbolsa_{h,m}$$

Los subíndices son: $i$ comercializador, $j$ mercado de comercialización, $n$ nivel de tensión, $m$ mes, $u$ usuario y $h$ hora.

### Equivalencia de variables

| Variable | Definición en la resolución | En este proyecto |
|----------|-----------------------------|------------------|
| $VE$ | Valoración del excedente en $. Es ingreso para el usuario cuando es mayor que cero | Total de factura con signo contrario |
| $Imp$ | Importación de energía acumulada en el mes, en kWh | $C$ |
| $EEHA$ | Excedentes horarios acumulados desde la primera hora del mes | $A_h$ |
| $hx$ | Hora en que $EEHA$ iguala o sobrepasa $Imp$ | Primera hora con $A_h \geq C$ |
| $Exc1$ | Excedente acumulado para crédito de energía, entre 0 e $Imp$ | $\min(I, C)$ |
| $Exc2$ | En $hx$ vale $EEHA - Imp$; en las horas siguientes, toda la energía entregada en esa hora | $q_h$ |
| $CUv$ | Componente variable del costo unitario, $/kWh | `tariffs.cu` |
| $Cv$ | Margen de comercialización, $/kWh | `tariffs.c` |
| $Pbolsa$ | Precio de bolsa de la hora, $/kWh | `xm_data_hourly_per_agent.value` |

## Signo de EE2

El enunciado indica que la tarifa de EE1 es el CU negativo, pero no da signo para EE2. La regulación lo resuelve: en $VE$, el término $Exc2 * Pbolsa$ suma, y $VE > 0$ es ingreso para el usuario. La factura se expresa desde el lado contrario (positivo es lo que paga el usuario), de modo que:

$$-VE = (Imp - Exc1) * CUv + Exc1 * Cv - \sum_{h} Exc2_h * Pbolsa_h$$

Separando términos:

- $Imp * CUv$ es EA.
- $-Exc1 * CUv$ es EE1.
- $Exc1 * Cv$ es EC, con la base que usa la regulación.
- $-\sum_h Exc2_h * Pbolsa_h$ es EE2, y por eso es **negativo**.

El signo está en la constante `EE2_SIGN` de `app/billing.py`. Si se requiere la lectura literal del enunciado (EE2 positivo), basta cambiar esa línea.

## Conciliación con la regulación

La prueba difiere de la regulación en un punto: cobra EC sobre toda la inyección ($I$), mientras que el literal a) cobra $Cv$ solo sobre $Exc1$. Se implementa lo que pide el enunciado, por ser explícito. Ambas bases coinciden cuando $I \leq C$.

| Servicio | $-VE$ (regulación) | Total de la prueba | Diferencia por base de EC |
|----------|--------------------|--------------------|---------------------------|
| 3222 | 17.196.464,27 | 17.196.464,27 | 0,00 |
| 2256 | −216.729,72 | −211.625,71 | 5.104,01 |
| 2478 | −160.873,23 | −156.925,28 | 3.947,95 |

La suite de tests verifica esta conciliación en `test_total_reconciles_with_regulated_value`.

## Supuestos

- `CU` es la suma de sus componentes: $CU = G + T + D + R + C + P$. Se cumple sin diferencia en las 105 filas de `tariffs`.
- Se aplica el literal a), porque los datos no incluyen la capacidad instalada de cada servicio. El literal b) se incluye como referencia.
- `value` de XM se toma como $Pbolsa$ ya ajustado; no se calcula el tope por precio de escasez.
- La Resolución CREG 101 072 de 2025 modificó el artículo 25 y cambió la valoración de EE2 a $MC_m$, con un régimen de transición que conserva el precio de bolsa (ver el [texto consolidado](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_creg_0174_2021.htm)). No afecta datos de 2023 ni el signo.
