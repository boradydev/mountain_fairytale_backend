CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE clients (
    client_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT NOT NULL,
    last_delivery_date TIMESTAMP NULL,
    last_delivery_quantity INTEGER NULL,
    cooldown_until TIMESTAMP NULL,
    sleeping_threshold_days INTEGER NOT NULL,
    sales_representative_id UUID NULL,
    default_payment_method_id UUID NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT clients_phone_key UNIQUE (phone),
    CONSTRAINT clients_sales_representative_id_fkey
        FOREIGN KEY (sales_representative_id)
        REFERENCES sales_representatives (sales_representative_id),
    CONSTRAINT clients_default_payment_method_id_fkey
        FOREIGN KEY (default_payment_method_id)
        REFERENCES payment_methods (payment_method_id)
);

CREATE INDEX ix_clients_name_trgm
    ON clients USING gin (name gin_trgm_ops);

CREATE INDEX ix_clients_phone_trgm
    ON clients USING gin (phone gin_trgm_ops);

CREATE INDEX ix_clients_address_trgm
    ON clients USING gin (address gin_trgm_ops);

CREATE INDEX ix_clients_created_at
    ON clients (created_at DESC, client_id DESC);
