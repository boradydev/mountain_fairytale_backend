CREATE TABLE cars (
    car_id UUID PRIMARY KEY,
    model TEXT NOT NULL,
    number TEXT NOT NULL UNIQUE,
    current_mileage DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX ix_cars_model
    ON cars (model);

CREATE INDEX ix_cars_number
    ON cars (number);
