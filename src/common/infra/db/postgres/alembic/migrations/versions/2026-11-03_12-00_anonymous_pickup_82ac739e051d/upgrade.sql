ALTER TABLE points ALTER COLUMN client_id DROP NOT NULL;

UPDATE point_commissions AS pc
SET sales_representative_id = NULL, commission_percent = 0, commission_payable = 0
FROM points AS p, delivery_documents AS d
WHERE pc.point_id = p.point_id
  AND p.delivery_document_id = d.delivery_document_id
  AND d.document_type = 'pickup_sheet';

-- Keep IDs, products, positions and the historical payment method unchanged.
UPDATE points AS p
SET client_id = NULL
FROM delivery_documents AS d
WHERE p.delivery_document_id = d.delivery_document_id
  AND d.document_type = 'pickup_sheet';

-- Invalidate any editor that loaded the legacy point representation.
UPDATE delivery_documents SET revision = revision + 1
WHERE document_type = 'pickup_sheet';
