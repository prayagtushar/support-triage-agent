-- A spoken ticket is the same ticket arriving through a channel that will not wait.
-- Same table, same routing, same audit trail: the voice work is a latency question,
-- not a second product, and giving it its own table would have implied otherwise.

ALTER TABLE tickets DROP CONSTRAINT tickets_channel_valid;

ALTER TABLE tickets ADD CONSTRAINT tickets_channel_valid CHECK (
    channel IN ('web', 'email', 'chat', 'voice')
);
