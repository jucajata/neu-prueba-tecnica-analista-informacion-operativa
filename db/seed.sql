-- Carga de datos de muestra. El orden respeta las llaves foráneas.
-- La ruta /data es el volumen de solo lectura definido en docker-compose.yml.

BEGIN;

COPY services (id_service, id_market, cdi, voltage_level)
    FROM '/data/services.csv' WITH (FORMAT csv, HEADER true);

-- En formato csv, un campo vacío se carga como NULL (cdi de niveles 2 y 3).
COPY tariffs (id_market, voltage_level, cdi, g, t, d, r, c, p, cu)
    FROM '/data/tariffs.csv' WITH (FORMAT csv, HEADER true);

COPY xm_data_hourly_per_agent (record_timestamp, value)
    FROM '/data/xm_data_hourly_per_agent.csv' WITH (FORMAT csv, HEADER true);

COPY records (id_record, id_service, record_timestamp)
    FROM '/data/records.csv' WITH (FORMAT csv, HEADER true);

COPY consumption (id_record, value)
    FROM '/data/consumption.csv' WITH (FORMAT csv, HEADER true);

COPY injection (id_record, value)
    FROM '/data/injection.csv' WITH (FORMAT csv, HEADER true);

ANALYZE;

COMMIT;
