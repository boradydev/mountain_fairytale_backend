CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE drivers (
    driver_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_drivers_name_trgm
    ON drivers USING gin (name gin_trgm_ops);
