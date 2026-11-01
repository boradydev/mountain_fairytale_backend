ALTER TABLE points
    ADD COLUMN payment_method_id UUID NULL;

ALTER TABLE points
    ADD CONSTRAINT points_payment_method_id_fkey
    FOREIGN KEY (payment_method_id)
    REFERENCES payment_methods(payment_method_id);

CREATE INDEX ix_points_payment_method_id ON points(payment_method_id);
