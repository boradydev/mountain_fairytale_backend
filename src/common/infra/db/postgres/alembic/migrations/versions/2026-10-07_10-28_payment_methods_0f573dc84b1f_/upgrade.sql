CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE payment_methods (
    payment_method_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT payment_methods_name_key UNIQUE (name)
);

CREATE INDEX ix_payment_methods_name_trgm
    ON payment_methods USING gin (name gin_trgm_ops);
