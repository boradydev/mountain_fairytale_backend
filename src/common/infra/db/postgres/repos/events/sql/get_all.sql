SELECT
    event_id,
    event_type,
    actor_id,
    created_at,
    payload
FROM events
ORDER BY created_at DESC, event_id DESC
OFFSET :offset
LIMIT :limit;