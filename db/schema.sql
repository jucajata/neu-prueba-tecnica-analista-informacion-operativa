-- Esquema del sistema de facturación de energía. Requiere PostgreSQL 15 o superior.
--
-- Montos y tarifas usan NUMERIC en lugar del float del diagrama para evitar
-- errores de redondeo binario en valores de dinero.

BEGIN;

CREATE TABLE services (
    id_service    INTEGER  PRIMARY KEY,
    id_market     INTEGER  NOT NULL,
    cdi           INTEGER,
    voltage_level SMALLINT NOT NULL,
    CONSTRAINT services_voltage_level_valid CHECK (voltage_level IN (1, 2, 3)),
    CONSTRAINT services_cdi_required_on_level_1 CHECK (voltage_level <> 1 OR cdi IS NOT NULL)
);

-- El diagrama marca id_market como PK, pero cada mercado tiene 5 tarifas.
-- La llave natural es (id_market, voltage_level, cdi), y cdi es NULL en los
-- niveles 2 y 3: de ahí la PK subrogada y NULLS NOT DISTINCT.
CREATE TABLE tariffs (
    id_tariff     INTEGER        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_market     INTEGER        NOT NULL,
    voltage_level SMALLINT       NOT NULL,
    cdi           INTEGER,
    g             NUMERIC(14, 8) NOT NULL,
    t             NUMERIC(14, 8) NOT NULL,
    d             NUMERIC(14, 8) NOT NULL,
    r             NUMERIC(14, 8) NOT NULL,
    c             NUMERIC(14, 8) NOT NULL,
    p             NUMERIC(14, 8) NOT NULL,
    cu            NUMERIC(14, 8) NOT NULL,
    CONSTRAINT tariffs_natural_key UNIQUE NULLS NOT DISTINCT (id_market, voltage_level, cdi),
    CONSTRAINT tariffs_voltage_level_valid CHECK (voltage_level IN (1, 2, 3)),
    CONSTRAINT tariffs_cdi_only_on_level_1 CHECK ((voltage_level = 1) = (cdi IS NOT NULL))
);

CREATE TABLE xm_data_hourly_per_agent (
    record_timestamp TIMESTAMP      PRIMARY KEY,
    value            NUMERIC(16, 10) NOT NULL
);

CREATE TABLE records (
    id_record        INTEGER   PRIMARY KEY,
    id_service       INTEGER   NOT NULL REFERENCES services (id_service),
    record_timestamp TIMESTAMP NOT NULL REFERENCES xm_data_hourly_per_agent (record_timestamp),
    -- Evita lecturas duplicadas y resuelve el filtro por servicio y mes.
    CONSTRAINT records_service_hour_unique UNIQUE (id_service, record_timestamp)
);

CREATE TABLE consumption (
    id_record INTEGER        PRIMARY KEY REFERENCES records (id_record) ON DELETE CASCADE,
    value     NUMERIC(14, 6) NOT NULL,
    CONSTRAINT consumption_value_non_negative CHECK (value >= 0)
);

CREATE TABLE injection (
    id_record INTEGER        PRIMARY KEY REFERENCES records (id_record) ON DELETE CASCADE,
    value     NUMERIC(14, 6) NOT NULL,
    CONSTRAINT injection_value_non_negative CHECK (value >= 0)
);

-- Soporta las consultas por hora de todo el sistema (/system-load).
CREATE INDEX records_timestamp_idx ON records (record_timestamp);

-- Concentra la regla de negocio: en niveles 2 y 3 el cdi no importa.
-- No se puede expresar como FK porque un servicio de nivel 2 o 3 puede tener
-- cualquier cdi y la tarifa lo tiene en NULL.
CREATE VIEW service_tariffs AS
SELECT s.id_service,
       t.id_tariff,
       t.g,
       t.t,
       t.d,
       t.r,
       t.c,
       t.p,
       t.cu
FROM services s
JOIN tariffs t
  ON t.id_market = s.id_market
 AND t.voltage_level = s.voltage_level
 AND (s.voltage_level IN (2, 3) OR t.cdi = s.cdi);

COMMIT;
