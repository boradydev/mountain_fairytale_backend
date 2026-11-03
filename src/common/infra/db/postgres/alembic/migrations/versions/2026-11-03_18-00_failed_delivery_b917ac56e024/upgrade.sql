ALTER TABLE points ADD COLUMN is_delivered boolean NOT NULL DEFAULT true;
ALTER TABLE points ADD COLUMN non_delivery_reason text NOT NULL DEFAULT '';

ALTER TABLE points ADD CONSTRAINT points_delivery_reason_check CHECK (
    (is_delivered AND non_delivery_reason = '') OR
    (NOT is_delivered AND length(trim(non_delivery_reason)) BETWEEN 1 AND 1000 AND client_id IS NOT NULL)
);
