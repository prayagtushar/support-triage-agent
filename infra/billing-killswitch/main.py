"""Detach billing when the budget is actually exceeded.

A GCP budget on its own only sends notifications. This subscriber is what makes
it a ceiling: at 100% of budget it removes the billing account from the project,
which stops every billable service.

This is deliberately blunt. The demo goes offline rather than accruing charges,
because at a 400 INR budget against an expected ~20 INR/month, anything that
reaches the threshold is a runaway, not growth. Recovery is manual and one
command: relink the billing account.
"""

from __future__ import annotations

import base64
import json
import logging
import os

import googleapiclient.discovery

log = logging.getLogger(__name__)
# The functions runtime configures the root logger before this module is
# imported, which makes a plain basicConfig() a silent no-op and drops every
# INFO line. force=True replaces those handlers. Without it the one log that
# proves this function made the right call is invisible.
logging.basicConfig(level=logging.INFO, force=True)

TARGET_PROJECT = os.environ["TARGET_PROJECT_ID"]


def handler(event: dict, _context: object) -> None:
    """Pub/Sub entry point. Budget notifications arrive base64-encoded in `data`."""
    raw = event.get("data")
    if not raw:
        log.warning("empty_notification")
        return

    payload = json.loads(base64.b64decode(raw).decode("utf-8"))
    cost = float(payload.get("costAmount", 0))
    budget = float(payload.get("budgetAmount", 0))

    # Budgets fire at every threshold, so most invocations are the 50% and 90%
    # warnings. Only the real overrun should act.
    if budget <= 0 or cost < budget:
        log.info("under_budget cost=%s budget=%s", cost, budget)
        return

    billing = googleapiclient.discovery.build("cloudbilling", "v1", cache_discovery=False)
    name = f"projects/{TARGET_PROJECT}"

    # Skipping an already-disabled project is an optimisation, not a safety
    # check. If this read fails we still cut billing: a kill switch that
    # declines to fire because it could not read state is not a kill switch.
    try:
        info = billing.projects().getBillingInfo(name=name).execute()
        if not info.get("billingEnabled"):
            log.info("billing_already_disabled project=%s", TARGET_PROJECT)
            return
    except Exception as exc:  # noqa: BLE001 - deliberately never fatal
        log.warning("billing_state_unreadable falling_through error=%s", exc)

    billing.projects().updateBillingInfo(name=name, body={"billingAccountName": ""}).execute()
    log.error(
        "BILLING_DISABLED project=%s cost=%s budget=%s", TARGET_PROJECT, cost, budget
    )
