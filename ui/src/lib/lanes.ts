import type { TicketStatus } from "./types";

/** The three lanes, as routes. Shared by the rail, which counts them, and the queue, which
 *  reads its lane from the URL so every lane is a link someone can send. */
export const LANES = [
  {
    path: "/",
    status: "in_review" as TicketStatus,
    label: "needs review",
    hint: "The agent drafted a reply but was not confident enough to send it.",
    dot: "bg-mustard-fill",
  },
  {
    path: "/escalated",
    status: "escalated" as TicketStatus,
    label: "escalated",
    hint: "Policy or low confidence says a human should own this, not just approve a draft.",
    dot: "bg-rust-fill",
  },
  {
    path: "/auto-replied",
    status: "auto_replied" as TicketStatus,
    label: "auto-replied",
    hint: "Confident and grounded enough to answer without a human.",
    dot: "bg-teal-fill",
  },
] as const;

export type Lane = (typeof LANES)[number];
