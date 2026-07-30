CREATE TABLE agent_runs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id            UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,

    classification       JSONB,
    retrieval            JSONB,
    draft                TEXT,
    draft_citations      JSONB,
    judge_scores         JSONB,
    composite_confidence REAL,
    route                TEXT,
    route_reason         TEXT,

    errors               JSONB NOT NULL DEFAULT '[]',
    latency_ms           JSONB NOT NULL DEFAULT '{}',
    token_usage          JSONB NOT NULL DEFAULT '{}',
    langfuse_trace_id    TEXT,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT agent_runs_route_valid CHECK (
        route IS NULL OR route IN ('auto_reply', 'human_review', 'escalate')
    )
);

CREATE INDEX agent_runs_ticket_created_at_idx ON agent_runs (ticket_id, created_at DESC);
CREATE INDEX agent_runs_created_at_idx ON agent_runs (created_at DESC);
