CREATE TABLE cars (
    car_id UUID PRIMARY KEY,
    model TEXT NOT NULL,
    number TEXT NOT NULL UNIQUE,
    current_mileage DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT cars_number_format_check
        CHECK (number ~ '^[АВЕКМНОРСТУХ][0-9]{3}[АВЕКМНОРСТУХ]{2}[0-9]{2,3}$')
);

CREATE INDEX ix_cars_model
    ON cars (model);

CREATE INDEX ix_cars_number
    ON cars (number);
