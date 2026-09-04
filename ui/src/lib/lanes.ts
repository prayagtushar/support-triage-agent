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
    hint: "A human owns this one. A rule or a low score took it out of the agent's hands.",
    dot: "bg-rust-fill",
  },
  {
    path: "/auto-replied",
    status: "auto_replied" as TicketStatus,
    label: "auto-replied",
    hint: "The draft cleared the threshold and went out on its own.",
    dot: "bg-teal-fill",
  },
] as const;

export type Lane = (typeof LANES)[number];
