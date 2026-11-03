ALTER TABLE products
    ADD COLUMN is_free_price boolean NOT NULL DEFAULT false,
    ADD CONSTRAINT products_free_price_base_price_check
        CHECK (NOT is_free_price OR base_price = 0);

ALTER TABLE delivery_document_items
    ADD COLUMN is_free_price boolean NOT NULL DEFAULT false,
    ADD COLUMN driver_note text NOT NULL DEFAULT '',
    ADD CONSTRAINT delivery_document_items_driver_note_check
        CHECK (char_length(driver_note) <= 1000 AND (is_free_price OR driver_note = ''));
