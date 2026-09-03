"""Seed topics for per-domain corpus generation.

Asking a model for "varied" examples collapses into the same three tickets, so the
variety is supplied rather than requested. Same reason as synthetic_topics.py, which
covers the two intents Bitext leaves empty on the e-commerce desk; this covers a whole
desk that has no real corpus at all.

Every case generated from these is marked source='synthetic' and the domain it belongs
to is marked provenance='synthetic', because a desk grounded entirely in machine text
cannot support the claims one grounded in real transcripts can.
"""

from __future__ import annotations

TECH_PRODUCT_CONTEXT = (
    "a consumer software and devices company: a cross-platform sync app on Windows, "
    "macOS, Android and iOS, plus the laptops, tablets and accessories it sells"
)

TECH_TOPICS: dict[str, tuple[str, ...]] = {
    "outage": (
        "every page returns a connection error across all devices and networks",
        "sign-in fails for an entire office while the status page shows green",
        "the mobile app shows offline even on a working connection",
        "the service is unreachable from one region but fine elsewhere",
        "everything stopped working immediately after a scheduled maintenance window",
        "the desktop client cannot reach the server while the website loads fine",
    ),
    "account_access": (
        "password reset email never arrives and the address is correct",
        "authenticator app was on a phone that has been lost",
        "account locked after repeated failed sign-in attempts",
        "single sign-on loops back to the login page forever",
        "a licence seat shows as used by someone who has left the company",
        "changing the registered email address on an account",
    ),
    "hardware": (
        "laptop will not power on and shows no charging light",
        "screen flickers and shows vertical lines after a drop",
        "battery drains from full to empty in under an hour",
        "keyboard keys stopped responding after a liquid spill",
        "device runs hot enough to be uncomfortable and the fan is loud",
        "docking station stops detecting external monitors intermittently",
    ),
    "software_bug": (
        "the app closes immediately when opening the settings screen",
        "exported files are empty although the export reports success",
        "sync silently drops changes made while offline",
        "dark mode setting resets to light every restart",
        "notifications duplicate themselves several times per event",
        "the search box returns nothing for terms that clearly exist",
    ),
    "how_to": (
        "moving an account and its data to a new laptop",
        "setting up automatic backups to an external drive",
        "sharing a folder with someone outside the organisation",
        "restoring a file to an earlier version",
        "turning off notifications for one device only",
        "changing which folders sync on a metered connection",
    ),
    "performance": (
        "initial sync of a large library takes many hours",
        "the app becomes unresponsive when a folder holds thousands of files",
        "startup takes minutes on an older but supported machine",
        "memory use grows steadily until the machine swaps",
        "uploads crawl while other applications have full bandwidth",
        "search results take tens of seconds to appear on a large account",
    ),
    "feature_request": (
        "a native Linux client",
        "selective sync at the individual file level",
        "end-to-end encryption for a specific folder",
        "a command line interface for scripted backups",
        "support for a much older operating system version",
        "scheduled sync windows so it pauses during work hours",
    ),
    "other": (
        "praise for a support agent who resolved something quickly",
        "a question about upgrading between plans mid-term",
        "a security researcher reporting a possible vulnerability",
        "asking to speak to a human rather than a chatbot",
        "a request to delete all data held about the customer",
        "confusion about which plan a company is currently on",
    ),
}

DOMAIN_TOPICS: dict[str, tuple[str, dict[str, tuple[str, ...]]]] = {
    "tech": (TECH_PRODUCT_CONTEXT, TECH_TOPICS),
}
