import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Confidence, IntentBadge, LanguageBadge, UrgencyBadge } from "../components/Badges";
import { listTickets } from "../lib/api";
import { relativeAge } from "../lib/format";
import type { TicketStatus } from "../lib/types";

const LANES: { key: TicketStatus; label: string; hint: string }[] = [
  { key: "in_review", label: "Needs review", hint: "The agent drafted a reply but was not confident enough to send it." },
  { key: "escalated", label: "Escalated", hint: "Policy or low confidence says a human should own this, not just approve a draft." },
  { key: "auto_replied", label: "Auto-replied", hint: "Confident and grounded enough to answer without a human." },
];

export default function Queues() {
  const [lane, setLane] = useState<TicketStatus>("in_review");
  const active = LANES.find((l) => l.key === lane)!;
  const { data, isPending, error } = useQuery({
    queryKey: ["tickets", lane],
    queryFn: () => listTickets(lane),
    refetchInterval: 10_000,
  });

  return (
    <div>
      <div className="mb-6 flex gap-1 border-b border-neutral-200 dark:border-neutral-800">
        {LANES.map((l) => (
          <button
            key={l.key}
            onClick={() => setLane(l.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              lane === l.key
                ? "border-neutral-900 text-neutral-900 dark:border-neutral-100 dark:text-neutral-100"
                : "border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-300"
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>

      <p className="mb-4 text-sm text-neutral-500">{active.hint}</p>

      {error && <p className="text-sm text-red-600">Could not reach the API: {String(error)}</p>}
      {isPending && <p className="text-sm text-neutral-500">Loading…</p>}

      {data && data.tickets.length === 0 && (
        <div className="rounded border border-dashed border-neutral-300 p-10 text-center text-sm text-neutral-500 dark:border-neutral-700">
          No tickets in {active.label.toLowerCase()}.
        </div>
      )}

      {data && data.tickets.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-neutral-500">
              <tr className="border-b border-neutral-200 dark:border-neutral-800">
                <th className="py-2 pr-4 font-medium">Subject</th>
                <th className="py-2 pr-4 font-medium">Intent</th>
                <th className="py-2 pr-4 font-medium">Urgency</th>
                <th className="py-2 pr-4 font-medium">Lang</th>
                <th className="py-2 pr-4 font-medium">Confidence</th>
                <th className="py-2 font-medium">Age</th>
              </tr>
            </thead>
            <tbody>
              {data.tickets.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-neutral-100 hover:bg-neutral-50 dark:border-neutral-900 dark:hover:bg-neutral-900"
                >
                  <td className="py-2 pr-4">
                    <Link to={`/tickets/${t.id}`} className="font-medium underline-offset-2 hover:underline">
                      {t.subject}
                    </Link>
                  </td>
                  <td className="py-2 pr-4"><IntentBadge intent={t.intent} /></td>
                  <td className="py-2 pr-4"><UrgencyBadge urgency={t.urgency} /></td>
                  <td className="py-2 pr-4"><LanguageBadge language={t.language} /></td>
                  <td className="py-2 pr-4"><Confidence value={t.composite_confidence} /></td>
                  <td className="py-2 text-neutral-500">{relativeAge(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
