-- SQL Data Loading Script for PostgreSQL / TimescaleDB (PS 3.2 AC Optimization)
-- 
-- DO NOT RUN AGAINST ANY DB WITHOUT OPERATOR REVIEW.
-- This script documents the exact mapping of generated synthetic parquet/csv extracts
-- to the backend/domain/ac_models.py SQLAlchemy models and TimescaleDB hypertables.

-- ==============================================================================
-- 1. ROOMS TABLE (Model: RoomModel -> rooms)
-- Source: output/rooms.csv
-- ==============================================================================
-- Mapping:
--   id            <- id
--   building      <- building
--   name          <- name
--   room_type     <- room_type
--   area_sqm      <- area_sqm
--   capacity      <- capacity
--   target_temp_c <- target_temp_c
--   min_temp_c    <- min_temp_c
--   max_temp_c    <- max_temp_c
--   is_critical   <- is_critical
-- ------------------------------------------------------------------------------
COPY rooms(id, building, name, room_type, area_sqm, capacity, target_temp_c, min_temp_c, max_temp_c, is_critical)
FROM '/path/to/synthetic_data/output/rooms.csv'
WITH (FORMAT csv, HEADER true);

-- ==============================================================================
-- 2. AC UNITS TABLE (Model: ACUnitModel -> ac_units)
-- Source: output/ac_units.csv
-- ==============================================================================
-- Mapping:
--   id        <- id
--   room_id   <- room_id
--   name      <- name
--   rated_kw  <- rated_kw
--   cop       <- cop
-- ------------------------------------------------------------------------------
COPY ac_units(id, room_id, name, rated_kw, cop)
FROM '/path/to/synthetic_data/output/ac_units.csv'
WITH (FORMAT csv, HEADER true);

-- ==============================================================================
-- 3. AC TELEMETRY HYPERTABLE (Model: ACTelemetryModel -> ac_telemetry)
-- Source: output/ac_telemetry.csv
-- ==============================================================================
-- Note: id generated via uuid_generate_v4() or composite key
-- Mapping:
--   room_id         <- room
--   ac_unit_id      <- ac_unit_id
--   timestamp       <- date_time
--   power_kw        <- power_kw
--   set_temp_c      <- set_temp_c
--   room_temp_c     <- room_temp_c
--   occupancy       <- occupancy
--   on_off_status   <- on_off_status
--   scheduled_hours <- scheduled_hours
-- ------------------------------------------------------------------------------
CREATE TEMP TABLE staging_ac_telemetry (
    room VARCHAR(50),
    ac_unit_id VARCHAR(50),
    date_time TIMESTAMP WITH TIME ZONE,
    power_kw FLOAT,
    set_temp_c FLOAT,
    room_temp_c FLOAT,
    occupancy INT,
    on_off_status VARCHAR(10),
    scheduled_hours BOOLEAN
);

COPY staging_ac_telemetry FROM '/path/to/synthetic_data/output/ac_telemetry.csv' WITH (FORMAT csv, HEADER true);

INSERT INTO ac_telemetry (id, room_id, ac_unit_id, timestamp, power_kw, set_temp_c, room_temp_c, occupancy, on_off_status, scheduled_hours)
SELECT 
    'tel-' || ac_unit_id || '-' || to_char(date_time, 'YYYYMMDDHH24MISS'),
    room,
    ac_unit_id,
    date_time,
    power_kw,
    set_temp_c,
    room_temp_c,
    occupancy,
    on_off_status,
    scheduled_hours
FROM staging_ac_telemetry;

DROP TABLE staging_ac_telemetry;

-- ==============================================================================
-- 4. OCCUPANCY READINGS (Model: OccupancyModel -> occupancy_readings)
-- Source: output/occupancy_readings.csv
-- ==============================================================================
COPY occupancy_readings(id, room_id, timestamp, headcount, confidence, is_synthetic)
FROM '/path/to/synthetic_data/output/occupancy_readings.csv'
WITH (FORMAT csv, HEADER true);

-- ==============================================================================
-- 5. WEATHER READINGS (Model: WeatherModel -> weather)
-- Source: output/weather.csv
-- ==============================================================================
COPY weather(id, timestamp, outdoor_temp_c, relative_humidity, solar_irradiance_wm2)
FROM '/path/to/synthetic_data/output/weather.csv'
WITH (FORMAT csv, HEADER true);

-- ==============================================================================
-- 6. GROUND TRUTH LABELS (Model: GroundTruthLabelModel -> ground_truth_labels)
-- Source: output/ground_truth_labels.csv
-- ==============================================================================
COPY ground_truth_labels(id, room_id, ac_unit_id, anomaly_type, start_time, end_time, severity)
FROM '/path/to/synthetic_data/output/ground_truth_labels.csv'
WITH (FORMAT csv, HEADER true);
