"""Bitext corpus mapping: their 27 intents onto our 8."""

from __future__ import annotations

INTENT_MAP: dict[str, str] = {
    "check_invoice": "billing",
    "get_invoice": "billing",
    "check_payment_methods": "billing",
    "payment_issue": "billing",
    "get_refund": "refund",
    "track_refund": "refund",
    "check_refund_policy": "refund",
    "check_cancellation_fee": "refund",
    "recover_password": "account_access",
    "registration_problems": "account_access",
    "switch_account": "account_access",
    "create_account": "account_access",
    "delete_account": "account_access",
    "edit_account": "account_access",
    "track_order": "shipping",
    "delivery_period": "shipping",
    "delivery_options": "shipping",
    "change_shipping_address": "shipping",
    "set_up_shipping_address": "shipping",
    "place_order": "how_to",
    "change_order": "how_to",
    "cancel_order": "how_to",
    "newsletter_subscription": "how_to",
    "complaint": "other",
    "review": "other",
    "contact_customer_service": "other",
    "contact_human_agent": "other",
}

TAXONOMY: tuple[str, ...] = (
    "billing",
    "refund",
    "account_access",
    "bug_report",
    "how_to",
    "shipping",
    "feature_request",
    "other",
)

# Bitext is consumer commerce: no defect or product-request cases. gen_synthetic.py fills both.
INTENTS_ABSENT_FROM_BITEXT: frozenset[str] = frozenset({"bug_report", "feature_request"})
