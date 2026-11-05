WITH filtered AS (
    SELECT p.*, d.planned_date, d.created_at, d.driver_id, d.car_id
    FROM points p
    JOIN delivery_documents d USING (delivery_document_id)
    JOIN clients c USING (client_id)
    WHERE d.document_type = 'delivery_route_sheet' AND d.is_active
      AND d.planned_date BETWEEN :date_from AND :date_to
      AND (:search = '' OR
          c.name ILIKE :pattern ESCAPE '\' OR c.address ILIKE :pattern ESCAPE '\'
          OR c.delivery_details ILIKE :pattern ESCAPE '\'
          OR p.snapshot_client_name ILIKE :pattern ESCAPE '\'
          OR p.snapshot_client_address ILIKE :pattern ESCAPE '\'
          OR p.snapshot_delivery_details ILIKE :pattern ESCAPE '\'
          OR (:digits <> '' AND (regexp_replace(c.phone, '[^0-9]', '', 'g') LIKE :phone_pattern
              OR regexp_replace(p.snapshot_phone, '[^0-9]', '', 'g') LIKE :phone_pattern)))
), page AS (
    SELECT * FROM filtered
    ORDER BY planned_date DESC, created_at DESC, delivery_document_id DESC, position, point_id
    OFFSET :offset LIMIT :limit
), records AS (
    SELECT p.point_id, p.client_id, p.delivery_document_id, p.position,
        p.snapshot_client_name AS client_name, p.snapshot_phone AS phone,
        p.snapshot_client_address AS client_address, p.snapshot_delivery_details AS delivery_details,
        p.snapshot_client_address || CASE WHEN p.snapshot_delivery_details <> ''
            THEN ' — ' || p.snapshot_delivery_details ELSE '' END AS address,
        p.snapshot_sales_representative_id AS sales_representative_id, rep.name AS sales_representative_name,
        p.planned_date, p.created_at, driver.name AS driver_name,
        car.model || ' ' || car.number AS car_model_and_number,
        p.is_delivered, p.non_delivery_reason, p.memo, p.payment_method_id, payment.name AS payment_method_name,
        goods.total_amount, goods.items,
        (SELECT COALESCE(sum(round(i.quantity * i.price, 2)), 0)::text
         FROM points all_points JOIN delivery_document_items i USING (point_id)
         WHERE all_points.delivery_document_id = p.delivery_document_id AND all_points.is_delivered) AS document_total_amount
    FROM page p
    LEFT JOIN sales_representatives rep ON rep.sales_representative_id = p.snapshot_sales_representative_id
    LEFT JOIN drivers driver USING (driver_id)
    LEFT JOIN cars car USING (car_id)
    LEFT JOIN payment_methods payment USING (payment_method_id)
    LEFT JOIN LATERAL (
        SELECT COALESCE(sum(round(i.quantity * i.price, 2)), 0)::text AS total_amount,
            COALESCE(jsonb_agg(jsonb_build_object(
                'item_id', i.item_id, 'product_id', i.product_id, 'product_name', i.product_name,
                'quantity', i.quantity, 'price', i.price::text, 'amount', round(i.quantity * i.price, 2)::text,
                'is_free_price', i.is_free_price, 'driver_note', i.driver_note
            ) ORDER BY i.product_name, i.product_id, i.item_id), '[]'::jsonb) AS items
        FROM delivery_document_items i WHERE i.point_id = p.point_id
    ) goods ON TRUE
)
SELECT (SELECT count(*) FROM filtered) AS total,
    COALESCE((SELECT jsonb_agg(to_jsonb(r) ORDER BY planned_date DESC, created_at DESC,
        delivery_document_id DESC, position, point_id) FROM records r), '[]'::jsonb) AS documents;
