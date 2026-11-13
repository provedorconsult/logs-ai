CREATE TABLE log_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    received_at timestamptz NOT NULL DEFAULT now(),
    occurred_at timestamptz,
    source text NOT NULL,
    severity smallint CHECK (severity BETWEEN 0 AND 7),
    message text NOT NULL,
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX log_events_received_at_idx ON log_events (received_at DESC);
