import type { Language, Route, Urgency } from "../lib/types";

/** Colour is information: teal healthy, mustard waiting, rust escalated, olive cited. */
const base =
  "inline-flex items-center rounded-[2px] px-1.5 py-0.5 text-[11px] font-medium leading-tight";

const URGENCY_STYLE: Record<Urgency, string> = {
  P1: "bg-rust-bg text-rust",
  P2: "bg-mustard-bg text-mustard",
  P3: "bg-paper-3 text-ink-2",
  P4: "bg-paper-3 text-ink-3",
};

const ROUTE_STYLE: Record<Route, string> = {
  auto_reply: "bg-teal-bg text-teal",
  human_review: "bg-mustard-bg text-mustard",
  escalate: "bg-rust-bg text-rust",
};

export function UrgencyBadge({ urgency }: { urgency: Urgency | null }) {
  if (!urgency) return null;
  return <span className={`${base} ${URGENCY_STYLE[urgency]}`}>{urgency}</span>;
}

export function IntentBadge({ intent }: { intent: string | null }) {
  if (!intent) {
    // A ticket with no intent failed classification; saying so beats an empty cell.
    return <span className={`${base} bg-rust-bg text-rust`}>unclassified</span>;
  }
  return <span className={`${base} bg-paper-3 text-ink-2`}>{intent.replace(/_/g, " ")}</span>;
}

/** English is the default and stays unlabelled; only a non-default is news. */
export function LanguageBadge({ language }: { language: Language | null }) {
  if (!language || language === "en") return null;
  return <span className={`${base} bg-olive-bg text-olive`}>{language}</span>;
}

export function RouteBadge({ route }: { route: Route | null }) {
  if (!route) return <span className={`${base} bg-paper-3 text-ink-3`}>pending</span>;
  return <span className={`${base} ${ROUTE_STYLE[route]}`}>{route.replace(/_/g, " ")}</span>;
}
