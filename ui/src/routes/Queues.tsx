import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { IntentBadge, LanguageBadge, UrgencyBadge } from "../components/Badges";
import { ConfidenceMeter } from "../components/Meter";
import { getPolicy, listTickets } from "../lib/api";
import { relativeAge } from "../lib/format";
import type { TicketStatus } from "../lib/types";

const LANES: {
  key: TicketStatus;
  label: string;
  hint: string;
  dot: string;
}[] = [
  {
    key: "in_review",
    label: "needs review",
    hint: "The agent drafted a reply but was not confident enough to send it.",
    dot: "bg-mustard-fill",
  },
  {
    key: "escalated",
    label: "escalated",
    hint: "Policy or low confidence says a human should own this, not just approve a draft.",
    dot: "bg-rust-fill",
  },
  {
    key: "auto_replied",
    label: "auto-replied",
    hint: "Confident and grounded enough to answer without a human.",
    dot: "bg-teal-fill",
  },
];

export default function Queues() {
  const [lane, setLane] = useState<TicketStatus>("in_review");
  const active = LANES.find((l) => l.key === lane)!;

  const { data: policy } = useQuery({ queryKey: ["policy"], queryFn: getPolicy });

  // One query per lane so every tab carries a live count, not just the open
  // one. useQueries rather than useQuery in a loop, which would be a hook call
  // inside a map.
  const results = useQueries({
    queries: LANES.map((l) => ({
      queryKey: ["tickets", l.key],
      queryFn: () => listTickets(l.key),
      refetchInterval: 10_000,
    })),
  });

  const lanes = LANES.map((l, i) => ({ ...l, query: results[i] }));
  const current = lanes.find((l) => l.key === lane)!.query;

  return (
    <div>
      <div className="mb-1 flex flex-wrap gap-6 border-b border-rule">
        {lanes.map((l) => {
          const count = l.query.data?.tickets.length;
          const selected = lane === l.key;
          return (
            <button
              key={l.key}
              onClick={() => setLane(l.key)}
              aria-current={selected ? "page" : undefined}
              className={`-mb-px flex items-center gap-2 border-b-2 pb-2 text-sm transition-colors ${
                selected ? "border-ink text-ink" : "border-transparent text-ink-3 hover:text-ink"
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${l.dot}`} aria-hidden />
              {l.label}
              <span className="tabular-nums text-ink-3">{count ?? "·"}</span>
            </button>
          );
        })}
      </div>

      <p className="prose-human mb-6 mt-3 text-sm text-ink-2">{active.hint}</p>

      {current.error && (
        <p className="text-sm text-rust">Could not reach the API. {String(current.error)}</p>
      )}
      {current.isPending && <p className="text-sm text-ink-3">Loading…</p>}

      {current.data && current.data.tickets.length === 0 && (
        <div className="rounded-[2px] border border-dashed border-rule-2 p-10 text-center">
          <p className="text-sm text-ink-2">Nothing in {active.label}.</p>
          <p className="prose-human mt-1 text-xs text-ink-3">
            {lane === "auto_replied"
              ? "The agent only answers without a human when the draft is grounded and scores above the threshold. On this corpus that is rare, and measured on the evals page."
              : "Submit a ticket and it will appear here once the pipeline finishes."}
          </p>
        </div>
      )}

      {current.data && current.data.tickets.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">
              Tickets in {active.label}, newest first
            </caption>
            <thead>
              <tr className="rule-row text-left">
                <th className="eyebrow py-2 pr-4 font-medium">subject</th>
                <th className="eyebrow py-2 pr-4 font-medium">intent</th>
                <th className="eyebrow py-2 pr-4 font-medium">urg</th>
                <th className="eyebrow py-2 pr-4 font-medium">lang</th>
                <th className="eyebrow py-2 pr-4 font-medium">confidence</th>
                <th className="eyebrow py-2 font-medium">age</th>
              </tr>
            </thead>
            <tbody>
              {current.data.tickets.map((t) => (
                <tr key={t.id} className="rule-row transition-colors hover:bg-paper-2">
                  <td className="max-w-[22rem] py-2.5 pr-4">
                    <Link
                      to={`/tickets/${t.id}`}
                      className="prose-human block truncate underline-offset-2 hover:underline"
                    >
                      {t.subject}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4">
                    <IntentBadge intent={t.intent} />
                  </td>
                  <td className="py-2.5 pr-4">
                    <UrgencyBadge urgency={t.urgency} />
                  </td>
                  <td className="py-2.5 pr-4">
                    <LanguageBadge language={t.language} />
                  </td>
                  <td className="py-2.5 pr-4">
                    <ConfidenceMeter value={t.composite_confidence} policy={policy} />
                  </td>
                  <td className="py-2.5 tabular-nums text-ink-3">{relativeAge(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {policy && (
            <p className="mt-4 text-xs text-ink-3">
              The notch on each bar is the {policy.thresholds.auto_reply} auto-reply
              threshold. Bars reaching it were eligible to answer without a human.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
