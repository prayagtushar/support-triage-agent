# Failure analysis

Written against the eval run of 2026-08-01, golden v0, 60 tickets.
Each entry: what happened, which component owns it, what I changed or chose not
to change, and what a real fix would take.

---

## 1. The corpus cannot ground a specific answer, and that caps everything

**What happened.** 25 of 60 drafts set `is_safe_fallback`, while only 5 tickets
had weak retrieval. The drafter declared itself ungrounded five times more
often than retrieval said it should.

**Owner: the data, not the drafter.** Bitext's "resolutions" are largely
templates — *"Please provide your account details and I'll look it up"*,
*"I'd be delighted to assist you in discovering our delivery methods"*. They
describe a support interaction rather than containing an answer. Retrieval
correctly finds a topically similar case; the case then turns out to say
nothing the drafter can stand on.

**What I changed.** Softened the drafter rule so that explaining a general
process counts as a real answer rather than a fallback. That recovered some
tickets but cannot fix the underlying gap.

**A real fix** is a knowledge base rather than a transcript corpus: help-centre
articles, policy documents, and canned resolutions with actual content. That is
a different data-sourcing project, and it is the single highest-leverage change
available to this system.

---

## 2. Auto-reply precision does not reach the bar it was designed against

**What happened.** The design set an auto-reply precision bar of 0.95. Measured
across the whole threshold sweep, the system reaches 0.727 at 0.85 and 0.778 at
0.90. At 0.95 it auto-replies to nothing at all, so precision is undefined.

**Owner: the system as a whole**, and downstream of failure 1.

**What I changed.** Raised the threshold from 0.85 to 0.90, which trades
coverage for safety: auto-replies fall from 22 to 9 while review recall rises
from 0.786 to 0.929.

**What I chose not to change.** I did not lower the bar to make the number look
met. The honest statement is that on this corpus auto-reply is not safe to
enable at the intended standard, and the README says so. A system that reports
0.78 against a stated 0.95 target is more useful than one that quietly redefines
the target.

---

## 3. The composite is overconfident in every bucket

**What happened.** The reliability diagram is below the diagonal everywhere:

| Bucket | n | Stated | Observed | Gap |
|---|---|---|---|---|
| 0.5–0.6 | 5 | 0.582 | 0.400 | −0.182 |
| 0.6–0.7 | 9 | 0.657 | 0.444 | −0.212 |
| 0.7–0.8 | 7 | 0.761 | 0.143 | −0.618 |
| 0.8–0.9 | 28 | 0.859 | 0.714 | −0.145 |
| 0.9–1.0 | 11 | 0.919 | 0.818 | −0.100 |

**Owner: the composite formula.** Its weights (0.5 judge, 0.3 classifier, 0.2
retrieval) were a guess, and two of the three inputs are optimistic by
construction. Classifier self-reported confidence sits at 0.9–0.95 almost
always, and retrieval similarity is a proxy for relevance rather than a measure
of whether the case answers the question.

**A real fix** is to fit the weights against outcomes instead of choosing them,
and to replace classifier self-confidence with something calibrated. The 0.7–0.8
bucket is the one to attack first: a −0.62 gap on 7 tickets is not noise, it is
a band where the system is systematically wrong about itself.

**Measured, 2026-08-08.** `scripts/ablate_judge.py` re-routes both stored eval
runs under reweighted composites — offline, no API calls, and gated by a
fidelity check that replays the shipped weights and requires all 60 recorded
routes back before reporting anything.

Best achievable auto-reply precision, per arm, across the threshold sweep:

| Arm | judge / clf / retr | run v1 | run v2 |
|---|---|---|---|
| full (as shipped) | 0.5 / 0.3 / 0.2 | 0.778 | 0.632 |
| no judge | 0.0 / 0.6 / 0.4 | 0.800 (n=5) | 0.585 |
| judge only | 1.0 / 0.0 / 0.0 | **0.800** | **0.667** |

**The judge-only arm beats the shipped composite in both runs.** That is the one
result stable across the pair, and it says the guess was worse than not
guessing: the classifier and retrieval terms dilute the judge rather than
supplement it. Both weaker inputs are optimistic by construction, so averaging
them into a better signal drags it toward their bias. Fitting the weights is
still the right fix, but the immediate finding is that 1.0 on the judge is a
better starting point than 0.5.

**What this does not settle: whether the judge is necessary.** The no-judge arm
looks *better* than shipped in v1 and clearly worse in v2, and its v1 figure
rests on 5 auto-replies. The same n=60 instability described in failure 7
swamps this comparison too, so "removing the judge costs precision" is not yet
supported by the numbers — only by the three interceptions in failure 4. The
ablation is free to re-run, so it should be the first thing re-measured once the
golden set passes 100.

One caveat on what was measured: the no-judge arm zeroes the judge's *weight*
while leaving the pipeline intact. It does not set `judge=None`, which would
trip the upstream-failure guard in `decide_route` and route everything to a
human — measuring the guard rather than the judge.

---

## 4. The judge is the strongest component and repeatedly saved the system

**What happened.** Three separate times during development the drafter invented
something and the judge caught it precisely:

- *"the cancellation link is usually included in your confirmation email"* —
  invented, cited nothing. Groundedness 1.
- *"Humne aapki transaction check ki hai"* (we have checked your transaction) —
  the agent has no account access. Groundedness 2.
- a refund reversal with a timeline attached, unsupported by any case.
  Groundedness 2.

Each time the composite fell and the router sent the ticket to a human instead
of a customer.

**Not a failure, recorded deliberately.** It is evidence that cross-model
judging is doing real work, and the reason to keep the judge on a different
vendor from the drafter. It is also the argument against trusting a single
model to both write and approve its own output.

---

## 5. Two golden labels are contested, and I did not settle them

**What happened.** The classifier disagrees with g043 (*"app English me hi khul
raha hai"*, labelled `how_to`, predicted `bug_report`) and g055 (*"invoice
download nahi ho raha"*, labelled `billing`, predicted `bug_report`). Both
predictions are defensible: a setting that does not persist is arguably a
defect, and a download button opening a blank page certainly is.

**Owner: the golden set.**

**What I chose not to change.** Adjusting labels so the exam agrees with the
system is how a golden set rots into meaninglessness. These stay contested and
flagged for review, and any change gets a changelog line.

---

## 6. Urgency is the weakest metric and has had no attention

**What happened.** Urgency accuracy sits at roughly 0.77 while intent reached
0.95. No prompt iteration has been spent on it.

**Owner: the classifier prompt.** The urgency definitions are written but never
tuned, and the confusions are mostly one step apart (P2 vs P3), which suggests
the boundary wording rather than the model.

**A real fix** is the same loop that took intent from 0.867 to 0.967: look at
the confusion, change one thing, re-measure. It is the cheapest remaining
improvement and it has simply not been done yet.

---

## 7. The headline metric is not stable at this sample size

**What happened.** I ran the suite twice with identical configuration at
threshold 0.90. Auto-reply precision came back 0.778 the first time and 0.500
the second. Review recall moved 0.786 to 0.821. Intent accuracy held at 0.950
both times.

**Owner: the eval design, not the system.** At a 0.90 threshold only about ten
tickets are auto-replied, so precision is a fraction over a denominator of ten.
One ticket flipping moves it by ten points. The metric I most want to quote is
the one measured on the fewest samples, which is exactly backwards.

**What this changes.** Growing the golden set to 100+ is not polish, it is a
precondition for the headline number to mean anything, and the same is true of
reporting a spread across repeated runs rather than a single figure. Intent
accuracy, measured across all 60 tickets, was stable to three decimal places
across both runs; that contrast is the whole lesson.

**What I chose not to do.** I did not pick the better of the two runs. Both are
in `evals/reports/`, and the README quotes the range rather than the flattering
end of it.

---

## Cross-cutting note on where the time went

Three separate provider limits shaped this build more than any modelling
decision: Groq's 100k tokens per day, Gemini's 1000 embeddings per day, and
Gemini's prepaid credits running out mid-run. Each surfaced as something that
looked like a bug in my code, and one of them cost twenty minutes because my
own error message omitted the underlying cause. Free tiers are a capacity
decision, not a billing detail, and they belong in the architecture diagram.
