# Invalid run: v3-drafter-budget-16384, 2026-09-03T12:06:18Z

Do not publish these numbers and do not use them as a gate baseline.

Two faults, either alone disqualifying:

1. **It did not test what its label says.** `DRAFTER_MAX_TOKENS=4096` in `api/.env`
   overrides the default in `app/config.py`, so the run used 4096 despite the label. The
   truncation errors in the rows name 4096 themselves.
2. **The drafter ran out of credit partway through.** 17 of 60 tickets failed with
   `sarvam/sarvam-105b returned 402`, starting at g044. Every metric after that point is
   measuring an unpaid account rather than a model.

32 of 60 rows have no draft: 15 truncated, 17 unpaid.

Re-run with credit on the account and `DRAFTER_MAX_TOKENS=16384` actually in force. Check
`GET /policy` or print `settings.drafter_max_tokens` before starting, because the label is
written by hand and the value is not.
