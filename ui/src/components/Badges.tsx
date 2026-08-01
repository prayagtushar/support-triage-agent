import type { Language, Route, Urgency } from "../lib/types";

// Urgency is the only place colour shouts. Everything else stays neutral so
// that a glance at a queue reads severity first.
const URGENCY_STYLE: Record<Urgency, string> = {
  P1: "bg-red-100 text-red-800 ring-red-300 dark:bg-red-950 dark:text-red-200 dark:ring-red-800",
  P2: "bg-amber-100 text-amber-900 ring-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:ring-amber-800",
  P3: "bg-neutral-100 text-neutral-700 ring-neutral-300 dark:bg-neutral-800 dark:text-neutral-300 dark:ring-neutral-700",
  P4: "bg-neutral-100 text-neutral-500 ring-neutral-200 dark:bg-neutral-800 dark:text-neutral-400 dark:ring-neutral-700",
};

const base =
  "inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset";
const neutral =
  "bg-neutral-100 text-neutral-700 ring-neutral-300 dark:bg-neutral-800 dark:text-neutral-300 dark:ring-neutral-700";

export function UrgencyBadge({ urgency }: { urgency: Urgency | null }) {
  if (!urgency) return null;
  return <span className={`${base} ${URGENCY_STYLE[urgency]}`}>{urgency}</span>;
}

export function IntentBadge({ intent }: { intent: string | null }) {
  if (!intent) return null;
  return <span className={`${base} ${neutral}`}>{intent.replace(/_/g, " ")}</span>;
}

export function LanguageBadge({ language }: { language: Language | null }) {
  if (!language || language === "en") return null;
  return <span className={`${base} ${neutral}`}>{language}</span>;
}

export function RouteBadge({ route }: { route: Route | null }) {
  if (!route) return <span className={`${base} ${neutral}`}>pending</span>;
  return <span className={`${base} ${neutral}`}>{route.replace(/_/g, " ")}</span>;
}

export function Confidence({ value }: { value: number | null }) {
  if (value === null || value === undefined)
    return <span className="text-neutral-400 tabular-nums">—</span>;
  return <span className="tabular-nums">{value.toFixed(2)}</span>;
}
