CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
ALTER TABLE delivery_document_items ADD COLUMN item_id uuid;
-- Preserve the subject UUID used by previously recorded row audit events.
UPDATE delivery_document_items SET item_id = uuid_generate_v5(point_id, product_id::text);
ALTER TABLE delivery_document_items ALTER COLUMN item_id SET NOT NULL;
ALTER TABLE delivery_document_items ALTER COLUMN item_id SET DEFAULT gen_random_uuid();
ALTER TABLE delivery_document_items DROP CONSTRAINT delivery_document_items_pkey;
ALTER TABLE delivery_document_items ADD PRIMARY KEY (item_id);
CREATE INDEX ix_document_items_point ON delivery_document_items (point_id);
CREATE UNIQUE INDEX uq_document_item_standard_product
    ON delivery_document_items (point_id, product_id) WHERE NOT is_free_price;
