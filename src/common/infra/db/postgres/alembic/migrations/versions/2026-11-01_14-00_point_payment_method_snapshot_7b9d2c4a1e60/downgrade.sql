DROP INDEX ix_points_payment_method_id;

ALTER TABLE points
    DROP CONSTRAINT points_payment_method_id_fkey;

ALTER TABLE points
    DROP COLUMN payment_method_id;
