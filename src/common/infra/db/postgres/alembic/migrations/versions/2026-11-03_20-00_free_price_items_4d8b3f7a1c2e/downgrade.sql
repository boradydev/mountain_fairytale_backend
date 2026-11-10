DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM products WHERE is_free_price)
       OR EXISTS (
           SELECT 1 FROM delivery_document_items
           WHERE is_free_price OR driver_note <> ''
       ) THEN
        RAISE EXCEPTION 'Cannot downgrade while free-price products or annotated route items exist.';
    END IF;
END
$$;

ALTER TABLE delivery_document_items
    DROP CONSTRAINT delivery_document_items_driver_note_check,
    DROP COLUMN driver_note,
    DROP COLUMN is_free_price;

ALTER TABLE products
    DROP CONSTRAINT products_free_price_base_price_check,
    DROP COLUMN is_free_price;
