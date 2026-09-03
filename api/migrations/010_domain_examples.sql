-- The three worked examples were the last domain-specific thing left in the prompt code.
-- Example 1 is a duplicate subscription charge and example 2 is a Hinglish crash on an
-- export button: both teach the classifier a shop's vocabulary. Example 3 is the only
-- one that transfers, because "it doesnt work" is nobody's domain.
--
-- Each desk keeps its own, including its own Hinglish example, since the corpus is
-- English and Hinglish and an example set that is entirely English teaches the
-- classifier that Hinglish is unusual.

ALTER TABLE domains ADD COLUMN classify_examples TEXT NOT NULL DEFAULT '';

UPDATE domains SET classify_examples =
'EXAMPLE 1
Subject: charged twice this month
Body: I see two charges of Rs 499 on my card statement for July. I only have one
subscription. Please check.
Output:
{"intent": "billing", "urgency": "P3", "language": "en", "sentiment": "frustrated",
 "confidence": 0.93, "rationale": "Duplicate charge on an active subscription; asking
 for investigation rather than demanding money back, so billing not refund."}

EXAMPLE 2
Subject: app crash ho raha hai
Body: jab bhi main export button dabata hoon app crash ho jata hai. kal se try kar
raha hoon, kuch bhi kaam nahi kar raha. please fix fast
Output:
{"intent": "bug_report", "urgency": "P2", "language": "hi-en", "sentiment": "frustrated",
 "confidence": 0.9, "rationale": "Reproducible crash on export blocking the user''s work
 since yesterday with no workaround mentioned."}

EXAMPLE 3
Subject: question
Body: it doesnt work
Output:
{"intent": "other", "urgency": "P4", "language": "en", "sentiment": "neutral",
 "confidence": 0.2, "rationale": "No product, feature, or symptom named; not enough
 information to place this in any specific category."}'
WHERE id = 'ecom';

UPDATE domains SET classify_examples =
'EXAMPLE 1
Subject: nothing loads since the update
Body: Since this morning every page shows a connection error, on my laptop and my
phone, both networks. My colleague says the same. Nothing works at all.
Output:
{"intent": "outage", "urgency": "P1", "language": "en", "sentiment": "frustrated",
 "confidence": 0.92, "rationale": "Total failure across devices, networks and more than
 one user, so scope is service-wide rather than a single broken action."}

EXAMPLE 2
Subject: laptop charge nahi ho raha
Body: kal se laptop charge nahi ho raha hai. cable badal ke dekha, dusre socket mein
bhi try kiya, light bhi nahi aa rahi. warranty mein hai abhi
Output:
{"intent": "hardware", "urgency": "P2", "language": "hi-en", "sentiment": "frustrated",
 "confidence": 0.91, "rationale": "Physical device will not charge with cable and socket
 already ruled out by the user; warranty mentioned, so an RMA path is likely."}

EXAMPLE 3
Subject: sync
Body: it works but takes forever now
Output:
{"intent": "performance", "urgency": "P3", "language": "en", "sentiment": "neutral",
 "confidence": 0.62, "rationale": "User states the action completes, so this is speed
 rather than a bug, but no figures or scope are given to size it."}'
WHERE id = 'tech';
