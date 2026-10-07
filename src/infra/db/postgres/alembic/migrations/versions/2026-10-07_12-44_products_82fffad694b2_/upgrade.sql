CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE products (
    product_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    base_price DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT products_name_key UNIQUE (name)
);

CREATE INDEX ix_products_name_trgm
    ON products USING gin (name gin_trgm_ops);
