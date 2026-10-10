CREATE TABLE delivery_documents (
    delivery_document_id UUID PRIMARY KEY,
    document_type VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    planned_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    driver_id UUID NULL,
    car_id UUID NULL,
    start_mileage DOUBLE PRECISION NULL,
    end_mileage DOUBLE PRECISION NULL,

    CONSTRAINT delivery_documents_document_type_check
        CHECK (document_type IN ('delivery_route_sheet', 'pickup_sheet')),

    CONSTRAINT delivery_documents_delivery_fields_check
        CHECK (
            (
                document_type = 'delivery_route_sheet'
                AND driver_id IS NOT NULL
                AND car_id IS NOT NULL
                AND start_mileage IS NOT NULL
            )
            OR
            (
                document_type = 'pickup_sheet'
                AND driver_id IS NULL
                AND car_id IS NULL
                AND start_mileage IS NULL
                AND end_mileage IS NULL
            )
        ),

    CONSTRAINT delivery_documents_mileage_check
        CHECK (
            end_mileage IS NULL
            OR (
                start_mileage IS NOT NULL
                AND end_mileage > start_mileage
            )
        ),

    CONSTRAINT delivery_documents_driver_id_fkey
        FOREIGN KEY (driver_id)
        REFERENCES drivers (driver_id),

    CONSTRAINT delivery_documents_car_id_fkey
        FOREIGN KEY (car_id)
        REFERENCES cars (car_id)
);

CREATE INDEX ix_delivery_documents_type_created_at
    ON delivery_documents (document_type, created_at ASC);

CREATE INDEX ix_delivery_documents_type_is_active_created_at
    ON delivery_documents (document_type, is_active, created_at ASC);


CREATE TABLE points (
    point_id UUID PRIMARY KEY,
    delivery_document_id UUID NOT NULL,
    client_id UUID NOT NULL,
    position INTEGER NOT NULL,

    CONSTRAINT points_delivery_document_id_fkey
        FOREIGN KEY (delivery_document_id)
        REFERENCES delivery_documents (delivery_document_id)
        ON DELETE CASCADE,

    CONSTRAINT points_client_id_fkey
        FOREIGN KEY (client_id)
        REFERENCES clients (client_id),

    CONSTRAINT points_delivery_document_id_client_id_key
        UNIQUE (delivery_document_id, client_id),

    CONSTRAINT points_delivery_document_id_position_key
        UNIQUE (delivery_document_id, position),

    CONSTRAINT points_position_check
        CHECK (position >= 0)
);

CREATE INDEX ix_points_delivery_document_id
    ON points (delivery_document_id);


CREATE TABLE delivery_document_items (
    point_id UUID NOT NULL,
    product_id UUID NOT NULL,
    quantity INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,

    CONSTRAINT delivery_document_items_pkey
        PRIMARY KEY (point_id, product_id),

    CONSTRAINT delivery_document_items_point_id_fkey
        FOREIGN KEY (point_id)
        REFERENCES points (point_id)
        ON DELETE CASCADE,

    CONSTRAINT delivery_document_items_product_id_fkey
        FOREIGN KEY (product_id)
        REFERENCES products (product_id),

    CONSTRAINT delivery_document_items_quantity_check
        CHECK (quantity > 0),

    CONSTRAINT delivery_document_items_price_check
        CHECK (price >= 0)
);


CREATE TABLE delivery_document_edit_locks (
    delivery_document_id UUID PRIMARY KEY,
    employee_id UUID NOT NULL,
    expires_at TIMESTAMP NOT NULL,

    CONSTRAINT delivery_document_edit_locks_document_id_fkey
        FOREIGN KEY (delivery_document_id)
        REFERENCES delivery_documents (delivery_document_id)
        ON DELETE CASCADE,

    CONSTRAINT delivery_document_edit_locks_employee_id_fkey
        FOREIGN KEY (employee_id)
        REFERENCES employees (employee_id)
);

CREATE INDEX ix_delivery_document_edit_locks_expires_at
    ON delivery_document_edit_locks (expires_at);