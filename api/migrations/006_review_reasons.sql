-- A note says what the reviewer thought; a reason says what was wrong with the
-- draft, in a vocabulary the eval suite can count. original_text keeps the
-- drafter's version next to an edit, because the diff is the signal.

ALTER TABLE review_actions ADD COLUMN reason        TEXT;
ALTER TABLE review_actions ADD COLUMN original_text TEXT;

UPDATE review_actions SET reason = 'other' WHERE action = 'reject' AND reason IS NULL;

ALTER TABLE review_actions ADD CONSTRAINT review_actions_reason_valid CHECK (
    reason IS NULL OR reason IN (
        'hallucinated',    -- asserted something no cited case supports
        'wrong_intent',    -- wrong kind of ticket
        'wrong_tone',      -- accurate, not sendable as written
        'missing_info',    -- correct as far as it goes, does not answer
        'not_answerable',  -- no draft could be right
        'other'
    )
);

ALTER TABLE review_actions ADD CONSTRAINT review_actions_reject_has_reason CHECK (
    action <> 'reject' OR reason IS NOT NULL
);

CREATE INDEX review_actions_reason_idx ON review_actions (reason) WHERE reason IS NOT NULL;
