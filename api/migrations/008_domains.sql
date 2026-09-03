-- Multiple ticketing systems in one deployment.
--
-- Domain was a single string in config, interpolated into two prompts. That made the
-- most load-bearing assumption in the system global: one corpus, one intent taxonomy,
-- one set of thresholds. A second desk needs its own of each, because "my order has not
-- arrived" and "my laptop will not boot" do not share a vocabulary, and retrieval that
-- crosses between them cites evidence from the wrong business.
--
-- The intent taxonomy moves out of a CHECK constraint and into a table, because it is
-- now per domain: a retailer has `shipping` and `refund`, an IT desk has `outage` and
-- `hardware`, and neither list is wrong. resolved_cases keeps a composite foreign key so
-- a case still cannot carry an intent its own domain does not define. The constraint did
-- real work and it keeps doing it, one level up.

CREATE TABLE domains (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    -- The phrase the classifier and drafter are given. Replaces settings.domain.
    description TEXT NOT NULL,
    -- Whether the cases behind this domain are real support transcripts or generated.
    -- Surfaced in the UI and the eval card rather than kept as a footnote: a domain
    -- grounded in machine text cannot carry the same claims as one grounded in Bitext.
    provenance  TEXT NOT NULL,
    sort_order  INT  NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT domains_provenance_valid CHECK (provenance IN ('real', 'synthetic'))
);

CREATE TABLE domain_intents (
    domain_id TEXT NOT NULL REFERENCES domains (id) ON DELETE CASCADE,
    intent    TEXT NOT NULL,
    label     TEXT NOT NULL,
    PRIMARY KEY (domain_id, intent)
);

INSERT INTO domains (id, name, description, provenance, sort_order) VALUES
    ('ecom', 'Consumer e-commerce',
     'a consumer online shopping service', 'real', 1),
    ('tech', 'Tech support desk',
     'a consumer software and devices support desk', 'synthetic', 2);

INSERT INTO domain_intents (domain_id, intent, label) VALUES
    ('ecom', 'billing',          'billing'),
    ('ecom', 'refund',           'refund'),
    ('ecom', 'account_access',   'account access'),
    ('ecom', 'bug_report',       'bug report'),
    ('ecom', 'how_to',           'how to'),
    ('ecom', 'shipping',         'shipping'),
    ('ecom', 'feature_request',  'feature request'),
    ('ecom', 'other',            'other'),

    ('tech', 'outage',           'outage'),
    ('tech', 'account_access',   'account access'),
    ('tech', 'hardware',         'hardware'),
    ('tech', 'software_bug',     'software bug'),
    ('tech', 'how_to',           'how to'),
    ('tech', 'performance',      'performance'),
    ('tech', 'feature_request',  'feature request'),
    ('tech', 'other',            'other');

-- Everything that exists today is the e-commerce desk. Backfill before the NOT NULL.
ALTER TABLE tickets ADD COLUMN domain_id TEXT REFERENCES domains (id);
UPDATE tickets SET domain_id = 'ecom' WHERE domain_id IS NULL;
ALTER TABLE tickets ALTER COLUMN domain_id SET NOT NULL;
ALTER TABLE tickets ALTER COLUMN domain_id SET DEFAULT 'ecom';

ALTER TABLE resolved_cases ADD COLUMN domain_id TEXT REFERENCES domains (id);
UPDATE resolved_cases SET domain_id = 'ecom' WHERE domain_id IS NULL;
ALTER TABLE resolved_cases ALTER COLUMN domain_id SET NOT NULL;
ALTER TABLE resolved_cases ALTER COLUMN domain_id SET DEFAULT 'ecom';

-- The taxonomy was eight e-commerce intents hardcoded in a CHECK. It is now whatever
-- the domain declares, still enforced, but by the domain rather than by the schema.
ALTER TABLE resolved_cases DROP CONSTRAINT resolved_cases_intent_valid;
ALTER TABLE resolved_cases ADD CONSTRAINT resolved_cases_intent_in_domain
    FOREIGN KEY (domain_id, intent) REFERENCES domain_intents (domain_id, intent);

-- Retrieval always filters by domain now, so every index it uses leads with it.
CREATE INDEX resolved_cases_domain_intent_idx ON resolved_cases (domain_id, intent);
CREATE INDEX tickets_domain_status_created_idx
    ON tickets (domain_id, status, created_at DESC);
