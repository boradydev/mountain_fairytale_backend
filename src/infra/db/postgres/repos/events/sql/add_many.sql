INSERT INTO events (
    event_id,
    event_type,
    actor_id,
    created_at,
    payload
)
VALUES (
    :event_id,
    :event_type,
    :actor_id,
    :created_at,
    CAST(:payload AS JSONB)
);