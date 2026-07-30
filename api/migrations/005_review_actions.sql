CREATE TABLE review_actions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id     UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    reviewer   TEXT NOT NULL DEFAULT 'prayag',
    action     TEXT NOT NULL,
    final_text TEXT,
    note       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT review_actions_action_valid CHECK (action IN ('approve', 'edit', 'reject')),
    CONSTRAINT review_actions_edit_has_text CHECK (
        action <> 'edit' OR (final_text IS NOT NULL AND length(trim(final_text)) > 0)
    )
);

CREATE INDEX review_actions_run_id_idx ON review_actions (run_id);
CREATE INDEX review_actions_created_at_idx ON review_actions (created_at DESC);
