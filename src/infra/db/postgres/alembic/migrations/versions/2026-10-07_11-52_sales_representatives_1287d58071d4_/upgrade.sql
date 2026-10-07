CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE sales_representatives (
    sales_representative_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    commission_percent DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT sales_representatives_phone_key UNIQUE (phone)
);

CREATE INDEX ix_sales_representatives_name_trgm
    ON sales_representatives USING gin (name gin_trgm_ops);

CREATE INDEX ix_sales_representatives_phone_trgm
    ON sales_representatives USING gin (phone gin_trgm_ops);
