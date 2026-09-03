# Eval summary: v3-drafter-budget-16384

Golden set `v0`, 60 tickets, 698.5s.

## Risk metrics

These two lead because they encode the asymmetry. A false auto-reply reaches a
customer; a missed review is a silent failure. Routing accuracy alone hides both.

| Metric | Value | Detail |
|---|---|---|
| **Auto-reply precision** | **0.667** | 4/6 |
| **Review recall** | **0.929** | 26/28 |
| Routing accuracy | 0.433 | |

## Component accuracy

| Metric | Value |
|---|---|
| Intent accuracy | 0.950 |
| Intent macro F1 | 0.953 |
| Intent, English only | 0.977 |
| Intent, Hinglish only | 0.867 |
| Urgency accuracy | 0.800 |
| Language accuracy | 1.000 |

| Behaviour | Rate |
|---|---|
| Safe fallback | 0.217 |
| Weak retrieval | 0.083 |

## Cost and latency

| Metric | Value |
|---|---|
| Cost per ticket | Rs 0.0495 |
| Mean end-to-end | 29711 ms |
| p50 | 33665 ms |
| p95 | 46524 ms |

## Calibration

Stated confidence against observed correctness. Points below the diagonal at
the high end are overconfidence, which is where it is dangerous.

| Bucket | n | Mean confidence | Observed correct |
|---|---|---|---|
| 0.0 to 0.1 | 32 | 0.000 | 0.500 |
| 0.5 to 0.6 | 1 | 0.589 | 0.000 |
| 0.6 to 0.7 | 1 | 0.615 | 0.000 |
| 0.7 to 0.8 | 3 | 0.750 | 0.333 |
| 0.8 to 0.9 | 17 | 0.857 | 0.294 |
| 0.9 to 1.0 | 6 | 0.923 | 0.667 |

## Threshold sweep

Hard rules (P1, weak retrieval, safe fallback) are held fixed; only the
composite band moves.

| Auto-reply threshold | Precision | Auto-replied | Review recall | Routing accuracy |
|---|---|---|---|---|
| 0.60 | 0.769 | 13 | 0.893 | 0.517 |
| 0.65 | 0.769 | 13 | 0.893 | 0.517 |
| 0.70 | 0.769 | 13 | 0.893 | 0.517 |
| 0.75 | 0.769 | 13 | 0.893 | 0.517 |
| 0.80 | 0.750 | 12 | 0.893 | 0.500 |
| 0.85 | 0.750 | 12 | 0.893 | 0.500 |
| 0.90 | 0.667 | 6 | 0.929 | 0.433 |
| 0.95 | 0.000 | 0 | 1.000 | 0.400 |

## Per intent

| Intent | Precision | Recall | F1 | n |
|---|---|---|---|---|
| billing | 0.88 | 0.88 | 0.88 | 8 |
| refund | 1.00 | 0.86 | 0.92 | 7 |
| account_access | 1.00 | 1.00 | 1.00 | 9 |
| bug_report | 0.80 | 1.00 | 0.89 | 8 |
| how_to | 1.00 | 0.88 | 0.93 | 8 |
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
- tickets with node errors: 32, fatal: 0
