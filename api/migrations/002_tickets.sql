CREATE TABLE tickets (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_ref  TEXT,
    channel       TEXT NOT NULL DEFAULT 'web',
    subject       TEXT NOT NULL,
    body          TEXT NOT NULL,
    customer_meta JSONB NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'received',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT tickets_channel_valid CHECK (channel IN ('web', 'email', 'chat')),
    CONSTRAINT tickets_status_valid CHECK (status IN (
        'received', 'triaged', 'auto_replied', 'in_review', 'resolved', 'escalated'
    ))
);

CREATE INDEX tickets_status_created_at_idx ON tickets (status, created_at DESC);
