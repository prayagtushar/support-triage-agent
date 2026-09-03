-- One boundary rule was lost when the guidance moved into the domain row in 009. It
-- separates how_to from shipping, which the eval notes list as a real confusion, so it
-- goes back rather than being quietly dropped.

UPDATE domains SET classify_guidance = classify_guidance ||
'
- "how do I change my saved address" is how_to. "my live order is going to the
  wrong address" is shipping.
- A request that mentions payment but asks where to click is how_to, not billing.'
WHERE id = 'ecom';
