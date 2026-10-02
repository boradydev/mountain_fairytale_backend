CREATE TABLE cars (
    car_id UUID PRIMARY KEY,
    model TEXT NOT NULL,
    number TEXT NOT NULL,
    current_mileage DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX ix_cars_model
    ON cars (model);

CREATE INDEX ix_cars_number
    ON cars (number);

-- Частичный уникальный индекс: номер должен быть уникален только среди активных авто
CREATE UNIQUE INDEX uq_cars_number_active 
    ON cars (number) 
    WHERE (is_active IS TRUE);
