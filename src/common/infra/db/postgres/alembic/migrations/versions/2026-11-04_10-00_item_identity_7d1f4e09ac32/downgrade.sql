DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM delivery_document_items GROUP BY point_id, product_id HAVING count(*) > 1)
       OR EXISTS (SELECT 1 FROM delivery_document_items WHERE item_id <> uuid_generate_v5(point_id, product_id::text)) THEN
        RAISE EXCEPTION 'Cannot downgrade while new row identities or repeated product rows exist';
    END IF;
END $$;
DROP INDEX uq_document_item_standard_product;
DROP INDEX ix_document_items_point;
ALTER TABLE delivery_document_items DROP CONSTRAINT delivery_document_items_pkey;
ALTER TABLE delivery_document_items ADD PRIMARY KEY (point_id, product_id);
ALTER TABLE delivery_document_items DROP COLUMN item_id;
