CREATE TABLE resolved_cases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent          TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'en',
    customer_text   TEXT NOT NULL,
    resolution_text TEXT NOT NULL,

    -- 1536, not 3072: pgvector's HNSW caps at 2000 dims
    embedding       VECTOR(1536),

    -- no Postgres config exists for romanized Hindi; hi-en rows match literally
    fts             TSVECTOR GENERATED ALWAYS AS
                      (to_tsvector('english', customer_text)) STORED,

    source          TEXT NOT NULL DEFAULT 'bitext',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT resolved_cases_intent_valid CHECK (intent IN (
        'billing', 'refund', 'account_access', 'bug_report',
        'how_to', 'shipping', 'feature_request', 'other'
    )),
    CONSTRAINT resolved_cases_language_valid CHECK (language IN ('en', 'hi-en', 'hi')),
    CONSTRAINT resolved_cases_source_valid CHECK (source IN ('bitext', 'synthetic', 'reviewer'))
);

CREATE INDEX resolved_cases_embedding_idx
    ON resolved_cases USING hnsw (embedding vector_cosine_ops);

CREATE INDEX resolved_cases_fts_idx ON resolved_cases USING gin (fts);

CREATE INDEX resolved_cases_intent_idx ON resolved_cases (intent);

CREATE INDEX resolved_cases_pending_embedding_idx
    ON resolved_cases (id) WHERE embedding IS NULL;
