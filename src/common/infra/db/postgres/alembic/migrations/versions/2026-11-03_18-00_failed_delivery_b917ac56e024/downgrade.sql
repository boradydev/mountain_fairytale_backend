DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM points WHERE NOT is_delivered) THEN
        RAISE EXCEPTION 'Restore unsuccessful deliveries before removing their state';
    END IF;
END $$;

ALTER TABLE points DROP CONSTRAINT points_delivery_reason_check;
ALTER TABLE points DROP COLUMN non_delivery_reason, DROP COLUMN is_delivered;
