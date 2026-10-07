CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor_id UUID NOT NULL,
    created_at TIMESTAMP NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX ix_events_created_at
    ON events (created_at DESC, event_id DESC);

CREATE INDEX ix_events_actor_id_created_at
    ON events (actor_id, created_at DESC, event_id DESC);