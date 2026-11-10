ALTER TABLE points
    ADD COLUMN snapshot_client_name text,
    ADD COLUMN snapshot_phone text,
    ADD COLUMN snapshot_client_address text,
    ADD COLUMN snapshot_delivery_details text,
    ADD COLUMN snapshot_sales_representative_id uuid REFERENCES sales_representatives(sales_representative_id);

-- Set based backfill, including cancelled routes; anonymous pickups remain NULL.
UPDATE points p SET snapshot_client_name = c.name, snapshot_phone = c.phone,
    snapshot_client_address = c.address, snapshot_delivery_details = c.delivery_details,
    snapshot_sales_representative_id = c.sales_representative_id
FROM clients c WHERE c.client_id = p.client_id;
