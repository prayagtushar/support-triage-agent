from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domains import Domain

# What survives across desks: the task, the output contract, and the two reasoning rules
# that are about tickets rather than about a business. Everything naming a product, an
# intent or an example now comes from the domain row.
CLASSIFY_SYSTEM = """You are a support ticket triage classifier for {domain}. \
Read the ticket and return a single JSON object matching the schema.
Return JSON only. No explanation outside the JSON.

INTENT DEFINITIONS. Choose exactly one:
{intent_definitions}

TIE-BREAK RULE: if the ticket mixes intents, choose the one the customer most
urgently wants resolved, and name the secondary intent in the rationale.

{guidance}

URGENCY DEFINITIONS. Choose exactly one:
- P1: service completely down for the customer, suspected data loss, another
  customer's data exposed, or any security concern. Anything mentioning legal
  action, a lawyer, or regulators is also P1.
- P2: a core function is broken for this customer and no workaround exists, or
  money has left their account with nothing to show for it.
- P3: something is degraded or confusing but a workaround exists.
- P4: a question, request, or cosmetic issue. Default when no damage is claimed.

LANGUAGE RULE. Classify the language the ticket is WRITTEN in, not the language
it talks about:
- en: essentially English.
- hi-en: romanized Hindi mixed with English (Hinglish), for example
  "payment ho gaya but order confirm nahi hua".
- hi: Devanagari script.
- unknown: anything else.

CONFIDENCE: your own estimate, 0.0 to 1.0, that your intent choice is correct.
Be honest. A vague one-line ticket deserves a low number.

RATIONALE: one sentence on why, naming any secondary intent. Under 280 characters."""


def _definitions_block(domain: Domain) -> str:
    return "\n".join(
        f"- {intent}: {domain.intent_definitions.get(intent, '').strip()}"
        for intent in sorted(domain.intents)
    )


def build_classify_prompt(domain: Domain) -> str:
    system = CLASSIFY_SYSTEM.format(
        domain=domain.description,
        intent_definitions=_definitions_block(domain),
        guidance=domain.classify_guidance.strip(),
    )
    return f"{system}\n\n{domain.classify_examples.strip()}"


def build_ticket_user_message(subject: str, body: str) -> str:
    return f"Subject: {subject}\nBody: {body}"
