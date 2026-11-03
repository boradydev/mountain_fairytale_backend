WITH eligible AS (
    SELECT d.* FROM delivery_documents d
    WHERE d.planned_date BETWEEN :date_from AND :date_to
      AND (d.is_active OR :include_cancelled)
), matching_points AS (
    SELECT p.point_id, p.delivery_document_id
    FROM points p
    JOIN eligible d ON d.delivery_document_id = p.delivery_document_id
    JOIN clients c ON c.client_id = p.client_id
    WHERE :search <> '' AND (
        c.name ILIKE :pattern ESCAPE '\'
        OR c.address ILIKE :pattern ESCAPE '\'
        OR (:digits <> '' AND regexp_replace(c.phone, '[^0-9]', '', 'g') LIKE :phone_pattern)
    )
), filtered AS (
    SELECT d.* FROM eligible d
    WHERE :search = '' OR EXISTS (
        SELECT 1 FROM matching_points m WHERE m.delivery_document_id = d.delivery_document_id
    )
), page AS (
    SELECT * FROM filtered
    ORDER BY planned_date DESC, created_at DESC, delivery_document_id DESC
    OFFSET :offset LIMIT :limit
), records AS (
    SELECT d.delivery_document_id,
           CASE d.document_type WHEN 'delivery_route_sheet' THEN 'deliveryRouteSheet' ELSE 'pickupSheet' END AS document_type,
           d.planned_date, d.created_at, d.is_active,
           driver.name AS driver_name,
           car.model || ' ' || car.number AS car_model_and_number,
           CASE WHEN d.document_type = 'delivery_route_sheet' THEN purchases.purchase_count ELSE 0 END AS clients_count,
           CASE WHEN d.document_type = 'pickup_sheet' THEN purchases.purchase_count ELSE 0 END AS purchases_count,
           round(purchases.total_amount, 2)::text AS total_amount,
           purchases.matched_clients
    FROM page d
    LEFT JOIN drivers driver ON driver.driver_id = d.driver_id
    LEFT JOIN cars car ON car.car_id = d.car_id
    LEFT JOIN LATERAL (
        SELECT count(*) AS purchase_count, COALESCE(sum(goods.total_amount), 0) AS total_amount,
               COALESCE(jsonb_agg(jsonb_build_object(
                   'point_id', p.point_id, 'client_id', c.client_id,
                   'client_name', c.name,
                   'address', c.address || CASE WHEN c.delivery_details <> '' THEN ' — ' || c.delivery_details ELSE '' END,
                   'phone', c.phone,
                   'payment_method_id', p.payment_method_id, 'payment_method_name', payment.name,
                   'total_amount', round(goods.total_amount, 2)::text, 'items', goods.items
               ) ORDER BY p.position) FILTER (WHERE m.point_id IS NOT NULL), '[]'::jsonb) AS matched_clients
        FROM points p
        LEFT JOIN clients c ON c.client_id = p.client_id
        LEFT JOIN matching_points m ON m.point_id = p.point_id
        LEFT JOIN payment_methods payment ON payment.payment_method_id = p.payment_method_id
        LEFT JOIN LATERAL (
            SELECT COALESCE(sum(round(i.quantity * i.price, 2)), 0) AS total_amount,
                   COALESCE(jsonb_agg(jsonb_build_object(
                       'product_id', i.product_id, 'product_name', i.product_name,
                       'quantity', i.quantity, 'price', i.price::text,
                       'amount', round(i.quantity * i.price, 2)::text
                   ) ORDER BY i.product_name, i.product_id), '[]'::jsonb) AS items
            FROM delivery_document_items i WHERE i.point_id = p.point_id
        ) goods ON TRUE
        WHERE p.delivery_document_id = d.delivery_document_id
    ) purchases ON TRUE
)
SELECT (SELECT count(*) FROM filtered) AS total,
       COALESCE((SELECT jsonb_agg(to_jsonb(r) ORDER BY planned_date DESC, created_at DESC, delivery_document_id DESC)
                 FROM records r), '[]'::jsonb) AS documents;
