SELECT d.delivery_document_id, d.created_at, d.planned_date, d.is_active,
       CASE d.document_type
           WHEN 'delivery_route_sheet' THEN 'deliveryRouteSheet'
           WHEN 'pickup_sheet' THEN 'pickupSheet'
       END AS document_type,
       d.driver_id, driver.name AS driver_name,
       d.car_id, car.model || ' ' || car.number AS car_model_and_number,
       d.start_mileage, d.end_mileage,
       COALESCE(document_points.points, '[]'::jsonb) AS points
FROM delivery_documents AS d
LEFT JOIN drivers AS driver ON driver.driver_id = d.driver_id
LEFT JOIN cars AS car ON car.car_id = d.car_id
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object(
        'point_id', p.point_id,
        'client_id', p.client_id,
        'client_name', client.name,
        'phone', client.phone,
        'address', client.address,
        'default_payment_method_id', client.default_payment_method_id,
        'default_payment_method_name', payment.name,
        'sales_representative_id', client.sales_representative_id,
        'sales_representative_name', representative.name,
        'position', p.position,
        'items', COALESCE(point_items.items, '[]'::jsonb)
    ) ORDER BY p.position) AS points
    FROM points AS p
    JOIN clients AS client ON client.client_id = p.client_id
    LEFT JOIN payment_methods AS payment ON payment.payment_method_id = client.default_payment_method_id
    LEFT JOIN sales_representatives AS representative
        ON representative.sales_representative_id = client.sales_representative_id
    LEFT JOIN LATERAL (
        SELECT jsonb_agg(jsonb_build_object(
            'product_id', i.product_id,
            'product_name', i.product_name,
            'quantity', i.quantity,
            'price', i.price
        ) ORDER BY i.product_id) AS items
        FROM delivery_document_items AS i
        WHERE i.point_id = p.point_id
    ) AS point_items ON TRUE
    WHERE p.delivery_document_id = d.delivery_document_id
) AS document_points ON TRUE
WHERE d.planned_date = :planned_date
  AND (d.is_active OR :include_cancelled)
ORDER BY d.is_active DESC, d.created_at ASC, d.delivery_document_id DESC;
