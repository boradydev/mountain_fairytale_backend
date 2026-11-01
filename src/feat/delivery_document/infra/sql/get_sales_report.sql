WITH filtered_lines AS (
    SELECT p.payment_method_id,
           i.product_id,
           i.product_name,
           i.quantity,
           round(i.quantity * i.price, 2) AS amount
    FROM delivery_documents AS d
    JOIN points AS p USING (delivery_document_id)
    JOIN delivery_document_items AS i USING (point_id)
    WHERE d.is_active
      AND d.planned_date BETWEEN :date_from AND :date_to
), product_totals AS (
    SELECT payment_method_id,
           product_id,
           string_agg(DISTINCT product_name, ' / ' ORDER BY product_name) AS product_name,
           SUM(quantity)::bigint AS quantity,
           SUM(amount) AS amount
    FROM filtered_lines
    GROUP BY payment_method_id, product_id
), method_cards AS (
    SELECT method.payment_method_id,
           method.name AS payment_method_name,
           method.is_active,
           product.product_id,
           product.product_name,
           COALESCE(product.quantity, 0)::bigint AS quantity,
           COALESCE(product.amount, 0.00::numeric) AS amount
    FROM payment_methods AS method
    LEFT JOIN product_totals AS product
      ON product.payment_method_id = method.payment_method_id
    WHERE method.is_active OR product.product_id IS NOT NULL
), unassigned_card AS (
    SELECT NULL::uuid AS payment_method_id,
           'Не указан'::text AS payment_method_name,
           NULL::boolean AS is_active,
           product.product_id,
           product.product_name,
           product.quantity,
           product.amount
    FROM product_totals AS product
    WHERE product.payment_method_id IS NULL
), cards AS (
    SELECT * FROM method_cards
    UNION ALL
    SELECT * FROM unassigned_card
), totals AS (
    SELECT COALESCE(SUM(quantity), 0)::bigint AS total_quantity,
           COALESCE(SUM(amount), 0.00::numeric) AS total_amount
    FROM filtered_lines
)
SELECT totals.total_quantity,
       totals.total_amount,
       cards.payment_method_id,
       cards.payment_method_name,
       cards.is_active,
       cards.product_id,
       cards.product_name,
       cards.quantity,
       cards.amount
FROM totals
LEFT JOIN cards ON TRUE
ORDER BY cards.payment_method_name COLLATE "C",
         cards.product_name COLLATE "C" NULLS FIRST,
         cards.product_id NULLS FIRST;
