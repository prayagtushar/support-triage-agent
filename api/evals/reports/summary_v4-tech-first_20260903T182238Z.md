# Eval summary: v4-tech-first

Golden set `tech_v0`, 24 tickets, 217.1s.

## Risk metrics

These two lead because they encode the asymmetry. A false auto-reply reaches a
customer; a missed review is a silent failure. Routing accuracy alone hides both.

| Metric | Value | Detail |
|---|---|---|
| **Auto-reply precision** | **0.333** | 3/9 |
| **Review recall** | **0.700** | 14/20 |
| Routing accuracy | 0.667 | |

## Component accuracy

| Metric | Value |
|---|---|
| Intent accuracy | 0.917 |
| Intent macro F1 | 0.925 |
| Intent, English only | 0.905 |
| Intent, Hinglish only | 1.000 |
| Urgency accuracy | 0.708 |
| Language accuracy | 1.000 |

| Behaviour | Rate |
|---|---|
| Safe fallback | 0.083 |
| Weak retrieval | 0.042 |

## Cost and latency

| Metric | Value |
|---|---|
| Cost per ticket | Rs 0.1006 |
| Mean end-to-end | 34531 ms |
| p50 | 31582 ms |
| p95 | 50595 ms |

## Calibration

Stated confidence against observed correctness. Points below the diagonal at
the high end are overconfidence, which is where it is dangerous.

| Bucket | n | Mean confidence | Observed correct |
|---|---|---|---|
| 0.7 to 0.8 | 4 | 0.791 | 0.750 |
| 0.8 to 0.9 | 10 | 0.859 | 0.900 |
| 0.9 to 1.0 | 10 | 0.918 | 0.400 |

## Threshold sweep

Hard rules (P1, weak retrieval, safe fallback) are held fixed; only the
composite band moves.

| Auto-reply threshold | Precision | Auto-replied | Review recall | Routing accuracy |
|---|---|---|---|---|
| 0.60 | 0.222 | 18 | 0.300 | 0.375 |
| 0.65 | 0.222 | 18 | 0.300 | 0.375 |
| 0.70 | 0.222 | 18 | 0.300 | 0.375 |
| 0.75 | 0.222 | 18 | 0.300 | 0.375 |
| 0.80 | 0.176 | 17 | 0.300 | 0.333 |
| 0.85 | 0.200 | 15 | 0.400 | 0.417 |
| 0.90 | 0.333 | 9 | 0.700 | 0.667 |
| 0.95 | 0.000 | 0 | 1.000 | 0.750 |

## Per intent

| Intent | Precision | Recall | F1 | n |
|---|---|---|---|---|
| account_access | 1.00 | 0.75 | 0.86 | 4 |
| feature_request | 1.00 | 1.00 | 1.00 | 1 |
| hardware | 1.00 | 1.00 | 1.00 | 4 |
| how_to | 1.00 | 1.00 | 1.00 | 2 |
| other | 1.00 | 0.75 | 0.86 | 4 |
| outage | 0.67 | 1.00 | 0.80 | 2 |
| performance | 1.00 | 1.00 | 1.00 | 3 |
| software_bug | 0.80 | 1.00 | 0.89 | 4 |

## Configuration

- classifier `openrouter/meta-llama/llama-3.3-70b-instruct`
- drafter `sarvam/sarvam-105b`
- judge `openrouter/google/gemini-2.5-flash-lite`
- embedding `openrouter/openai/text-embedding-3-small`
- thresholds: auto-reply 0.9, review 0.55
- weak retrieval floor 0.4
- tickets with node errors: 0, fatal: 0
