# Invalid run: four-arm voice benchmark, 2026-09-03T19:02Z

Do not publish these numbers.

The speech account ran out of credit partway through the first arm. Every call after
that returned `402 insufficient_quota_error`, and speech-to-text is the first step of a
turn, so a turn that could not transcribe produced no latency at all rather than a slow
one.

| Arm | turns that completed |
|---|---|
| baseline | 36 of 60 |
| judge_async | 1 of 60 |
| stream_draft | 0 of 60 |
| fast_drafter | 0 of 60 |

The baseline p50 of 29.8s is measured on the 36 that survived, and the three arms the
benchmark exists to compare have no data at all. A table showing 0.0s for three arms is
not a speed result, it is an unpaid account, which is the same trap the quarantined eval
run in `../../reports/invalid/` fell into.

Re-run `make voice-bench` with credit on the account. Budget for it: one run is 60
text-to-speech calls to synthesise the prompts, then 240 turns each costing a
speech-to-text call, a full pipeline and one or more text-to-speech calls.
