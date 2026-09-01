import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ErrorNote, Skeleton } from "../components/Async";
import { IntentBadge, LanguageBadge, UrgencyBadge } from "../components/Badges";
import { ConfidenceMeter } from "../components/Meter";
import { listTickets } from "../lib/api";
import { ageTone, relativeAge } from "../lib/format";
import type { Lane } from "../lib/lanes";
import type { QueueRow } from "../lib/types";
import { usePolicy } from "../lib/usePolicy";

type Sort = "age" | "confidence" | "urgency";

const URGENCY_RANK = { P1: 0, P2: 1, P3: 2, P4: 3 } as const;

const INTRO_KEY = "triage-intro-dismissed";

/** One screen of orientation for someone who arrived from a link and has read nothing. */
function Intro({ startAt }: { startAt: string | undefined }) {
  const [hidden, setHidden] = useState(() => {
    try {
      return window.localStorage.getItem(INTRO_KEY) === "1";
    } catch {
      return false;
    }
  });

  if (hidden) return null;

  return (
    <div className="mb-6 rounded-[2px] border border-rule bg-paper-2 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="prose-human max-w-2xl space-y-2 text-sm text-ink-2">
          <p>
            These are a consumer shopping app's tickets — orders, refunds, double charges,
            lockouts, app crashes — in English and Hinglish. Each was classified, matched
            against resolved cases, answered with a drafted reply and graded by a second model
            on a different vendor. Fixed policy then put it in one of three lanes. Nothing below
            was written for display: it is what the pipeline recorded.
          </p>
          <p>
            The bar in the confidence column has a notch on it. That notch is the threshold
            above which the agent is allowed to answer without a human, so each row shows both
            a score and the distance that score sat from the decision it drove.
          </p>
        </div>
        <button
          onClick={() => {
            setHidden(true);
            try {
              window.localStorage.setItem(INTRO_KEY, "1");
            } catch {
              /* private windows still get the dismissal, just not the memory of it */
            }
          }}
          className="text-[11px] text-ink-3 underline-offset-2 hover:text-ink hover:underline"
        >
          dismiss
        </button>
      </div>

      {startAt && (
        <Link
          to={`/tickets/${startAt}`}
          className="mt-3 inline-block rounded-[2px] border border-rule-2 px-2.5 py-1.5 text-xs transition-colors hover:border-ink-3"
        >
          Start with the least confident one →
        </Link>
      )}
    </div>
  );
}

function sortRows(rows: QueueRow[], sort: Sort): QueueRow[] {
  const copy = [...rows];
  if (sort === "confidence") {
    return copy.sort((a, b) => (a.composite_confidence ?? 0) - (b.composite_confidence ?? 0));
  }
  if (sort === "urgency") {
    return copy.sort(
      (a, b) =>
        (a.urgency ? URGENCY_RANK[a.urgency] : 9) - (b.urgency ? URGENCY_RANK[b.urgency] : 9),
    );
  }
  return copy.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

export default function Queues({ lane }: { lane: Lane }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("age");
  const policy = usePolicy();

  const { data, error, isPending } = useQuery({
    queryKey: ["tickets", lane.status],
    queryFn: () => listTickets(lane.status),
    refetchInterval: 10_000,
  });

  const rows = data?.tickets;

  const visible = useMemo(() => {
    if (!rows) return [];
    const q = query.trim().toLowerCase();
    const matched = q
      ? rows.filter((t) =>
          `${t.subject} ${t.intent ?? ""} ${t.urgency ?? ""}`.toLowerCase().includes(q),
        )
      : rows;
    return sortRows(matched, sort);
  }, [rows, query, sort]);

  // The handoff is easiest to see where the agent was least sure, so that is where a
  // first-time reader is pointed rather than at whatever happens to be newest.
  const startAt = useMemo(
    () =>
      [...(rows ?? [])].sort(
        (a, b) => (a.composite_confidence ?? 1) - (b.composite_confidence ?? 1),
      )[0]?.id,
    [rows],
  );

  return (
    <div>
      {lane.status === "in_review" && <Intro startAt={startAt} />}

      <header className="mb-4 space-y-1">
        <h1 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <span className={`h-2 w-2 rounded-full ${lane.dot}`} aria-hidden />
          {lane.label}
          {rows && <span className="tabular-nums text-sm text-ink-3">{rows.length}</span>}
        </h1>
        <p className="prose-human max-w-2xl text-sm text-ink-2">{lane.hint}</p>
      </header>

      {rows && rows.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            type="search"
            placeholder="filter by subject, intent or urgency"
            aria-label="Filter tickets"
            className="prose-human w-full rounded-[2px] border border-rule bg-paper-2 px-2 py-1.5 text-xs sm:w-72"
          />
          <label className="flex items-center gap-2 text-[11px] text-ink-3">
            sort
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
              className="rounded-[2px] border border-rule bg-paper-2 px-1.5 py-1 text-[11px] text-ink"
            >
              <option value="age">newest</option>
              <option value="confidence">least confident</option>
              <option value="urgency">most urgent</option>
            </select>
          </label>
          {query && (
            <span className="text-[11px] tabular-nums text-ink-3">
              {visible.length} of {rows.length}
            </span>
          )}
        </div>
      )}

      {error && <ErrorNote error={error} what="the queue" />}
      {isPending && <Skeleton />}

      {rows && rows.length === 0 && (
        <div className="rounded-[2px] border border-dashed border-rule-2 p-10 text-center">
          <p className="text-sm text-ink-2">Nothing in {lane.label}.</p>
          <p className="prose-human mt-1 text-xs text-ink-3">
            {lane.status === "auto_replied"
              ? "The agent only answers without a human when the draft is grounded and scores above the threshold. On this corpus that is rare, and measured on the evals page."
              : "Send a ticket and it will appear here once the pipeline finishes."}
          </p>
        </div>
      )}

      {rows && rows.length > 0 && visible.length === 0 && (
        <p className="prose-human py-8 text-center text-sm text-ink-2">
          Nothing in this lane matches “{query}”.
        </p>
      )}

      {visible.length > 0 && (
        <>
          {/* Cards below sm, table above: a six-column table on a phone is a horizontal
              scrollbar pretending to be a layout. */}
          <ul className="space-y-px sm:hidden">
            {visible.map((t) => (
              <li key={t.id}>
                <Link to={`/tickets/${t.id}`} className="rule-row block py-3">
                  <span className="prose-human block text-sm">{t.subject}</span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-2">
                    <IntentBadge intent={t.intent} />
                    <UrgencyBadge urgency={t.urgency} />
                    <LanguageBadge language={t.language} />
                    <ConfidenceMeter value={t.composite_confidence} policy={policy} width="w-14" />
                    <span
                      className={`ml-auto text-xs tabular-nums ${ageTone(t.created_at, t.urgency)}`}
                    >
                      {relativeAge(t.created_at)}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>

          <div className="hidden sm:block">
            <table className="w-full text-sm">
              <caption className="sr-only">Tickets in {lane.label}</caption>
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
                {visible.map((t) => (
                  <tr key={t.id} className="rule-row group transition-colors hover:bg-paper-2">
                    <td className="max-w-[22rem] py-2.5 pr-4">
                      <Link
                        to={`/tickets/${t.id}`}
                        className="prose-human flex items-center gap-1.5 truncate underline-offset-2 hover:underline"
                      >
                        <span className="truncate">{t.subject}</span>
                        <span
                          aria-hidden
                          className="text-ink-3 opacity-0 transition-opacity group-hover:opacity-100"
                        >
                          →
                        </span>
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
                    <td className={`py-2.5 tabular-nums ${ageTone(t.created_at, t.urgency)}`}>
                      {relativeAge(t.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {policy && (
            <p className="prose-human mt-4 max-w-2xl text-xs text-ink-3">
              The notch on each bar is the {policy.thresholds.auto_reply} auto-reply threshold.
              Bars reaching it were eligible to answer without a human. Age turns amber once a
              ticket is past the response window for its priority, which most of the seeded
              corpus is.
            </p>
          )}
        </>
      )}
    </div>
  );
}
