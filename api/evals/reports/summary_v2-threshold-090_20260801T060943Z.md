# Eval summary: v2-threshold-090

Golden set `v0`, 60 tickets, 369.5s.

## Risk metrics

These two lead because they encode the asymmetry. A false auto-reply reaches a
customer; a missed review is a silent failure. Routing accuracy alone hides both.

| Metric | Value | Detail |
|---|---|---|
| **Auto-reply precision** | **0.500** | 5/10 |
| **Review recall** | **0.821** | 23/28 |
| Routing accuracy | 0.417 | |

## Component accuracy

| Metric | Value |
|---|---|
| Intent accuracy | 0.950 |
| Intent macro F1 | 0.953 |
| Intent, English only | 0.977 |
| Intent, Hinglish only | 0.867 |
| Urgency accuracy | 0.767 |
| Language accuracy | 1.000 |

| Behaviour | Rate |
|---|---|
| Safe fallback | 0.233 |
| Weak retrieval | 0.100 |

## Cost and latency

| Metric | Value |
|---|---|
| Cost per ticket | Rs 0.0499 |
| Mean end-to-end | 24224 ms |
| p50 | 21786 ms |
| p95 | 48100 ms |

## Calibration

Stated confidence against observed correctness. Points below the diagonal at
the high end are overconfidence, which is where it is dangerous.

| Bucket | n | Mean confidence | Observed correct |
|---|---|---|---|
| 0.5 to 0.6 | 5 | 0.580 | 0.400 |
| 0.6 to 0.7 | 6 | 0.637 | 0.500 |
| 0.7 to 0.8 | 13 | 0.757 | 0.385 |
| 0.8 to 0.9 | 25 | 0.856 | 0.360 |
| 0.9 to 1.0 | 11 | 0.916 | 0.545 |

## Threshold sweep

Hard rules (P1, weak retrieval, safe fallback) are held fixed; only the
composite band moves.

| Auto-reply threshold | Precision | Auto-replied | Review recall | Routing accuracy |
|---|---|---|---|---|
| 0.60 | 0.550 | 40 | 0.357 | 0.517 |
| 0.65 | 0.579 | 38 | 0.429 | 0.550 |
| 0.70 | 0.583 | 36 | 0.464 | 0.550 |
| 0.75 | 0.625 | 32 | 0.571 | 0.583 |
| 0.80 | 0.615 | 26 | 0.643 | 0.550 |
| 0.85 | 0.632 | 19 | 0.750 | 0.500 |
| 0.90 | 0.500 | 10 | 0.821 | 0.417 |
| 0.95 | 0.000 | 0 | 1.000 | 0.417 |

## Per intent

| Intent | Precision | Recall | F1 | n |
|---|---|---|---|---|
| billing | 1.00 | 0.88 | 0.93 | 8 |
| refund | 1.00 | 1.00 | 1.00 | 7 |
| account_access | 0.90 | 1.00 | 0.95 | 9 |
| bug_report | 0.80 | 1.00 | 0.89 | 8 |
| how_to | 1.00 | 0.75 | 0.86 | 8 |
| shipping | 1.00 | 1.00 | 1.00 | 7 |
| feature_request | 1.00 | 1.00 | 1.00 | 6 |
| other | 1.00 | 1.00 | 1.00 | 7 |

## Configuration

- classifier `openrouter/meta-llama/llama-3.3-70b-instruct`
- drafter `sarvam/sarvam-105b`
- judge `openrouter/google/gemini-2.5-flash-lite`
- embedding `openrouter/openai/text-embedding-3-small`
- thresholds: auto-reply 0.9, review 0.55
- weak retrieval floor 0.4
- tickets with node errors: 0, fatal: 0
