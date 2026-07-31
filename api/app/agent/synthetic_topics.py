"""Seed topics for synthetic corpus generation.

Diversity is steered by topic rather than by asking a model for "varied"
examples, which collapses onto the same three or four scenarios.
"""

from __future__ import annotations

BUG_REPORT_TOPICS: tuple[str, ...] = (
    "order confirmation email never arrives after checkout",
    "app crashes when opening the order history screen",
    "cart empties itself when switching between mobile and desktop",
    "product images fail to load on the category page",
    "search returns unrelated products for exact model numbers",
    "discount code is accepted but the total does not change",
    "saved delivery address reverts to an old one at checkout",
    "push notifications for delivery updates stopped arriving",
    "wishlist items disappear after logging out and back in",
    "payment page spins forever on one particular card",
    "order total shows the wrong currency after changing country",
    "invoice PDF downloads as a blank file",
    "quantity selector jumps back to one when scrolling",
    "two-factor code arrives after it has already expired",
    "review submission fails silently with no error shown",
    "tracking link opens someone else's order",
    "filters reset every time you go back from a product page",
    "app shows items in stock that are actually sold out",
    "profile photo upload rejects valid JPEG files",
    "delivery slot picker shows dates in the wrong timezone",
)

FEATURE_REQUEST_TOPICS: tuple[str, ...] = (
    "dark mode for the mobile app",
    "reorder a previous order in one tap",
    "save multiple delivery addresses with nicknames",
    "notify me when an out-of-stock item returns",
    "split payment across two cards",
    "export order history as a spreadsheet",
    "schedule deliveries for a specific time window",
    "wishlist sharing with family members",
    "in-app chat with a support agent",
    "subscribe to repeat deliveries of the same item",
    "filter search results by delivery speed",
    "gift wrapping and a gift note at checkout",
    "compare two products side by side",
    "voice search in Hindi",
    "price drop alerts on saved items",
    "a widget on the home screen for order tracking",
    "buy now pay later at checkout",
    "return pickup scheduling from the app",
    "loyalty points balance visible on the home screen",
    "offline browsing of recently viewed products",
)

PRODUCT_CONTEXT = (
    "a consumer online shopping app and website that sells physical goods, "
    "with accounts, orders, payments, delivery tracking, and refunds"
)
