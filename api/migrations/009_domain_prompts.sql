-- The taxonomy moved into a table in 008. Its meaning has to follow.
--
-- The classifier prompt carried eight intent definitions, a set of boundary rules and
-- three worked examples, all of them about a shop. "Which payment methods do you accept
-- is about payment, so billing" is excellent guidance and useless to an IT desk. Leaving
-- it in code would have meant a second domain silently classified against the first
-- one's vocabulary, which is the failure this whole change exists to prevent.
--
-- README calls the domain "configuration, not an assumption". Until now that was one
-- phrase interpolated into two prompts. This is the rest of it.

ALTER TABLE domain_intents ADD COLUMN definition TEXT NOT NULL DEFAULT '';
ALTER TABLE domains ADD COLUMN classify_guidance TEXT NOT NULL DEFAULT '';

UPDATE domain_intents SET definition = v.definition
FROM (VALUES
  ('ecom','billing','charges, invoices, payment methods, pricing, double charges, being charged after cancelling. The customer is asking about money going OUT to you, not money coming back.'),
  ('ecom','refund','the customer wants money back for something already paid, or is asking about a refund already requested. Money coming BACK to them.'),
  ('ecom','account_access','cannot log in, password reset, two-factor problems, locked or suspended accounts, closing an account, changing the registered email.'),
  ('ecom','bug_report','the product misbehaves. Errors, crashes, wrong results, features not working as documented.'),
  ('ecom','how_to','the customer wants instructions for using a product feature that works as designed. Choose this only when no other category names the subject.'),
  ('ecom','shipping','delivery status, delivery options, address changes on a live order, damaged, late, or missing physical items.'),
  ('ecom','feature_request','the customer asks for something the product does not do.'),
  ('ecom','other','none of the above fits. Includes praise, general complaints about service, requests to speak to a human, and sales enquiries. Use sparingly and explain in rationale.'),

  ('tech','outage','the service is down or unreachable for the user, or they believe it is. Total failures, cannot connect, everything is broken, error pages on every action. Distinguished from software_bug by scope: nothing works rather than one thing works wrongly.'),
  ('tech','account_access','cannot sign in, password or passkey reset, multi-factor problems, locked or suspended accounts, permissions and licence seats, changing the registered email.'),
  ('tech','hardware','physical devices. Will not power on, screen, keyboard, battery, overheating, peripherals, docks, cables, physical damage, warranty and RMA.'),
  ('tech','software_bug','the software misbehaves in a specific, reproducible way. Crashes on one action, wrong output, a feature not working as documented. One thing is broken rather than everything.'),
  ('tech','how_to','the user wants instructions for something that already works as designed: configuration, setup, where a setting lives. Choose this only when no other category names the subject.'),
  ('tech','performance','it works but too slowly. Lag, long load times, timeouts under load, sync taking hours, high memory or CPU. The action completes, eventually.'),
  ('tech','feature_request','the user asks for something the product does not do, or asks for support on a platform or version that is not supported.'),
  ('tech','other','none of the above fits. Includes praise, billing and licensing enquiries, requests for a human, and security reports. Use sparingly and explain in rationale.')
) AS v(domain_id, intent, definition)
WHERE domain_intents.domain_id = v.domain_id AND domain_intents.intent = v.intent;

UPDATE domains SET classify_guidance =
'CLASSIFY THE SUBJECT, NOT THE GRAMMAR. Most tickets are phrased as questions.
Being a question does not make a ticket how_to. Ask what the ticket is ABOUT:
- "which payment methods do you accept" is about payment, so billing.
- "what is your return policy" is about getting money back, so refund.
- "how do I change my account email" is about the account, so account_access.
- "where do I leave a review" is about none of the product categories, so other.
- "can you notify me when items restock" asks for a capability, so feature_request.
Reach for how_to only when the subject itself is operating a feature that already
works, such as "where is the cancel button".

BOUNDARIES THAT ARE COMMONLY CONFUSED:
- "charged twice, reverse one" is billing: the ask is investigating a charge.
  "I returned it, where is my money" is refund.
- A late parcel is shipping, not bug_report, even when the tracking page errors.'
WHERE id = 'ecom';

UPDATE domains SET classify_guidance =
'CLASSIFY THE SUBJECT, NOT THE GRAMMAR. Most tickets are phrased as questions.
Being a question does not make a ticket how_to. Ask what the ticket is ABOUT:
- "why is sync taking three hours" is about speed, so performance.
- "the app closes when I open settings" is one broken action, so software_bug.
- "nothing loads on any device since this morning" is total, so outage.
- "my laptop will not charge" is a physical device, so hardware.
- "how do I turn on dark mode" is operating a working feature, so how_to.
- "do you support Linux" asks for a capability, so feature_request.

BOUNDARIES THAT ARE COMMONLY CONFUSED:
- SCOPE separates outage from software_bug. Everything failing is outage; one
  action failing is software_bug. When the user reports both, ask whether any
  part of the product still works for them.
- SPEED separates performance from software_bug. If the action completes and is
  merely slow, it is performance. If it never completes or completes wrongly, it
  is software_bug.
- A device that will not power on is hardware even when the user blames an
  update. A crash on a working device is software_bug even when they blame the
  hardware. Classify the evidence, not the theory.
- Cannot sign in is account_access, not outage, unless the user reports the
  service is down for everyone rather than for them.'
WHERE id = 'tech';
