WITH bounds AS (
    SELECT MIN(planned_date) AS first_date,
           GREATEST(CURRENT_DATE, MAX(planned_date)) AS last_date
    FROM delivery_documents
), calendar_range AS (
    SELECT first_date, last_date,
           COALESCE(last_date - first_date + 1, 0) AS total
    FROM bounds
), calendar_page AS (
    -- Generate only the requested calendar page, including dates without documents.
    SELECT last_date - CAST(day_offset AS integer) AS planned_date
    FROM calendar_range
    CROSS JOIN LATERAL generate_series(
        CAST(LEAST(total, CAST(:offset AS numeric)) AS bigint),
        CAST(LEAST(total - 1, CAST(:offset AS numeric) + CAST(:limit AS numeric) - 1) AS bigint)
    ) AS series(day_offset)
), active_documents AS (
    SELECT d.delivery_document_id, d.document_type, d.planned_date
    FROM delivery_documents AS d
    JOIN calendar_page AS c USING (planned_date)
    WHERE d.is_active
), point_counts AS (
    -- Count points before joining item rows to avoid multiplying visits.
    SELECT d.planned_date,
           COUNT(*) FILTER (WHERE d.document_type = 'delivery_route_sheet') AS delivery_points_count,
           COUNT(*) FILTER (WHERE d.document_type = 'pickup_sheet') AS pickup_points_count
    FROM active_documents AS d
    JOIN points AS p USING (delivery_document_id)
    GROUP BY d.planned_date
), product_totals AS (
    SELECT d.planned_date, i.product_id,
           string_agg(DISTINCT i.product_name COLLATE "C", ' / '
                      ORDER BY i.product_name COLLATE "C") AS product_name,
           SUM(i.quantity) AS quantity,
           -- Convert the saved float through its text representation: a direct
           -- float-to-numeric cast can lose digits near a half-cent boundary.
           SUM(round(i.quantity * CAST(CAST(i.price AS text) AS numeric), 2)) AS total_amount
    FROM active_documents AS d
    JOIN points AS p USING (delivery_document_id)
    JOIN delivery_document_items AS i USING (point_id)
    GROUP BY d.planned_date, i.product_id
), day_products AS (
    SELECT planned_date,
           jsonb_agg(jsonb_build_object(
               'product_id', product_id,
               'product_name', product_name,
               'quantity', quantity
           ) ORDER BY product_id) AS products,
           SUM(total_amount) AS total_amount
    FROM product_totals
    GROUP BY planned_date
), day_cards AS (
    SELECT c.planned_date,
           COALESCE(p.delivery_points_count, 0) AS delivery_points_count,
           COALESCE(p.pickup_points_count, 0) AS pickup_points_count,
           COALESCE(t.products, '[]'::jsonb) AS products,
           COALESCE(t.total_amount, 0) AS total_amount
    FROM calendar_page AS c
    LEFT JOIN point_counts AS p USING (planned_date)
    LEFT JOIN day_products AS t USING (planned_date)
)
-- Aggregating the page separately preserves total when offset is beyond the range.
SELECT r.total,
       COALESCE((SELECT jsonb_agg(to_jsonb(c) ORDER BY c.planned_date DESC)
                 FROM day_cards AS c), '[]'::jsonb) AS delivery_days
FROM calendar_range AS r;
