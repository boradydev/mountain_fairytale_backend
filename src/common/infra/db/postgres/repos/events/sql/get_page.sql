SELECT e.*, actor.username AS actor_name,
       document_subject.document_type AS document_type,
       COALESCE(names.display_name, employee_subject.username) AS subject_name,
       CASE
           WHEN e.event_type = 'EmployeeLoginEvent' THEN 'login'
           WHEN e.event_type = 'EmployeePasswordChangedEvent' THEN 'password_changed'
           WHEN e.event_type = 'CancelDeliveryDocumentEvent' THEN 'cancelled'
           WHEN e.event_type = 'RestoreDeliveryDocumentEvent' THEN 'restored'
           WHEN e.event_type LIKE 'Create%' THEN 'created'
           WHEN e.event_type LIKE 'Delete%' THEN 'deleted'
           WHEN e.event_type LIKE 'Update%' AND e.payload->'changes' =
               jsonb_build_object('is_active', jsonb_build_object('old', true, 'new', false)) THEN 'deactivated'
           WHEN e.event_type LIKE 'Update%' AND e.payload->'changes' =
               jsonb_build_object('is_active', jsonb_build_object('old', false, 'new', true)) THEN 'activated'
           WHEN e.event_type LIKE 'Update%' THEN 'updated'
           ELSE 'other'
       END AS action
FROM events e
LEFT JOIN employees actor ON actor.employee_id = e.actor_id
LEFT JOIN delivery_documents document_subject ON e.payload->>'subject_type' = 'delivery_document'
    AND document_subject.delivery_document_id::text = e.payload->>'subject_id'
LEFT JOIN employees employee_subject ON e.payload->>'subject_type' = 'employee'
    AND employee_subject.employee_id::text = e.payload->>'subject_id'
LEFT JOIN LATERAL (
    SELECT string_agg(value #>> '{}', ' ' ORDER BY ord) AS display_name
    FROM jsonb_array_elements_text(COALESCE(e.payload->'name_fields', '[]'::jsonb))
         WITH ORDINALITY AS fields(field, ord)
    LEFT JOIN LATERAL (
        SELECT COALESCE(h.payload->'changes'->fields.field->'new', h.payload->'data'->fields.field) AS value
        FROM events h
        WHERE h.payload->>'subject_type' = e.payload->>'subject_type'
          AND h.payload->>'subject_id' = e.payload->>'subject_id'
          AND (h.created_at, h.event_id) <= (e.created_at, e.event_id)
          AND ((h.payload->'changes') ? fields.field OR (h.payload->'data') ? fields.field)
        ORDER BY h.created_at DESC, h.event_id DESC
        LIMIT 1
    ) history ON TRUE
) names ON TRUE
WHERE (CAST(:before_at AS timestamptz) IS NULL OR
       (e.created_at, e.event_id) < (CAST(:before_at AS timestamptz), CAST(:before_id AS uuid)))
  AND (CAST(:after_at AS timestamptz) IS NULL OR
       (e.created_at, e.event_id) > (CAST(:after_at AS timestamptz), CAST(:after_id AS uuid)))
  AND (:search = '' OR strpos(lower(concat_ws(' ', actor.username,
       COALESCE(names.display_name, employee_subject.username), e.payload->>'subject_type',
       e.payload->'data', (e.payload->'changes') - 'password_hash' - 'password')), :search) > 0)
ORDER BY CASE WHEN CAST(:newer AS boolean) THEN e.created_at END ASC,
         CASE WHEN CAST(:newer AS boolean) THEN e.event_id END ASC,
         e.created_at DESC, e.event_id DESC
LIMIT :limit;
