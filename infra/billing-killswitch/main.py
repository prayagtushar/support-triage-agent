"""Detach billing at 100% of budget. A GCP budget alone only notifies; this makes it a ceiling."""

from __future__ import annotations

import base64
import json
import logging
import os

import googleapiclient.discovery

log = logging.getLogger(__name__)
# force=True because the functions runtime already configured the root logger.
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

    # Budgets fire at every threshold; only the real overrun should act.
    if budget <= 0 or cost < budget:
        log.info("under_budget cost=%s budget=%s", cost, budget)
        return

    billing = googleapiclient.discovery.build("cloudbilling", "v1", cache_discovery=False)
    name = f"projects/{TARGET_PROJECT}"

    # An optimisation, not a safety check: if this read fails, still cut billing.
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
