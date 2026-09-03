import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ErrorNote, Skeleton } from "../components/Async";
import { IntentBadge, LanguageBadge, UrgencyBadge } from "../components/Badges";
import { ConfidenceMeter } from "../components/Meter";
import { listTickets } from "../lib/api";
import { ageTone, relativeAge } from "../lib/format";
import type { Lane } from "../lib/lanes";
import type { QueueRow } from "../lib/types";
import { usePolicy } from "../lib/usePolicy";
import { useDomain } from "../lib/domain";

type Sort = "age" | "confidence" | "urgency";
type Density = "comfortable" | "compact";

const SORTS: readonly Sort[] = ["age", "confidence", "urgency"];
const DENSITY_KEY = "triage-density";

/** Per-viewer comfort, so it belongs to the browser rather than to the URL. */
function useDensity(): [Density, (d: Density) => void] {
  const [density, setDensity] = useState<Density>(() => {
    try {
      return window.localStorage.getItem(DENSITY_KEY) === "compact" ? "compact" : "comfortable";
    } catch {
      return "comfortable";
    }
  });

  return [
    density,
    (next: Density) => {
      setDensity(next);
      try {
        window.localStorage.setItem(DENSITY_KEY, next);
      } catch {
        // A browser refusing storage is not a reason to refuse the setting.
      }
    },
  ];
}

const URGENCY_RANK = { P1: 0, P2: 1, P3: 2, P4: 3 } as const;

const INTRO_KEY = "triage-intro-dismissed";

/** One screen of orientation for someone who arrived from a link and has read nothing. */
function Intro({
  startAt,
  domain,
  intents,
}: {
  startAt: string | undefined;
  domain: string | undefined;
  intents: string[];
}) {
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
            These are the tickets of {domain ?? "a consumer online shopping service"}
            {/* Drawn from the desk rather than listed in prose. The old copy named orders
                and refunds, which stopped being true the moment a second desk existed. */}
            {intents.length > 0 && <> — {intents.join(", ")}</>} — in English and Hinglish.
            The desk is a row in the database, not an assumption baked into a prompt, because
            “my order has not arrived” means something different to a retailer and a bank, and
            each desk carries its own cases, its own intents and its own worked examples. Each
            ticket was classified, matched against resolved cases from this desk only, answered
            with a drafted reply and graded by a second model on a different vendor. Fixed
            policy then put it in one of three lanes. Nothing below was written for display: it
            is what the pipeline recorded.
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
  // Filter and sort live in the URL: a lane filtered down to the two tickets worth
  // arguing about is the thing an operator wants to send someone, and useState made
  // that unshareable and lost it on reload.
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const sortParam = params.get("sort");
  const sort: Sort = SORTS.includes(sortParam as Sort) ? (sortParam as Sort) : "age";

  const setParam = (key: string, value: string, fallback: string) => {
    const next = new URLSearchParams(params);
    if (!value || value === fallback) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const [density, setDensity] = useDensity();
  const rowPad = density === "compact" ? "py-1" : "py-2.5";
  const policy = usePolicy();
  const { id: domainId, domain } = useDomain();

  const { data, error, isPending } = useQuery({
    // The desk is part of the key, so switching desks refetches rather than showing the
    // previous desk's rows under the new desk's name.
    queryKey: ["tickets", lane.status, domainId],
    queryFn: () => listTickets(lane.status, domainId),
    enabled: Boolean(domainId),
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
      {lane.status === "in_review" && (
        <Intro
          startAt={startAt}
          domain={domain?.description ?? policy?.domain}
          intents={(domain?.intents ?? []).map((i) => domain?.intent_labels[i] ?? i)}
        />
      )}

      {domain && !domain.ready && (
        <div
          role="status"
          className="mb-6 rounded-[2px] border border-rust/40 bg-rust-bg px-3 py-2 text-xs text-rust"
        >
          <span className="font-medium">{domain.name} has no evidence behind it.</span>{" "}
          <span className="prose-human">
            No resolved cases are embedded for this desk, so retrieval returns nothing and
            every draft would be ungrounded. Tickets sent here are routed to a human by
            hard rule, which is correct, and tells you nothing about the agent.
          </span>
        </div>
      )}

      {domain?.provenance === "synthetic" && domain.ready && (
        <div
          role="status"
          className="mb-6 rounded-[2px] border border-mustard/40 bg-mustard-bg px-3 py-2 text-xs text-mustard"
        >
          <span className="font-medium">Generated desk.</span>{" "}
          <span className="prose-human">
            Every case behind {domain.name} was written by a model, so drafts here are
            machine text grounded in machine text and graded by a third machine. It shows
            the routing works per desk. It is not evidence of quality on this domain.
          </span>
        </div>
      )}

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
            onChange={(e) => setParam("q", e.target.value, "")}
            type="search"
            placeholder="filter by subject, intent or urgency"
            aria-label="Filter tickets"
            className="prose-human w-full rounded-[2px] border border-rule bg-paper-2 px-2 py-1.5 text-xs sm:w-72"
          />
          <label className="flex items-center gap-2 text-[11px] text-ink-3">
            sort
            <select
              value={sort}
              onChange={(e) => setParam("sort", e.target.value, "age")}
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

          {/* Clearing a lane is the job, so someone working one wants rows on screen
              rather than air between them. */}
          <div
            role="group"
            aria-label="Row density"
            className="ml-auto hidden overflow-hidden rounded-[2px] border border-rule sm:flex"
          >
            {(["comfortable", "compact"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setDensity(option)}
                aria-pressed={density === option}
                className={`px-2 py-1 text-[11px] transition-colors ${
                  density === option
                    ? "bg-paper-3 text-ink"
                    : "bg-paper-2 text-ink-3 hover:text-ink-2"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
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
                    <td className={`max-w-[22rem] pr-4 ${rowPad}`}>
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
                    <td className={`pr-4 ${rowPad}`}>
                      <IntentBadge intent={t.intent} />
                    </td>
                    <td className={`pr-4 ${rowPad}`}>
                      <UrgencyBadge urgency={t.urgency} />
                    </td>
                    <td className={`pr-4 ${rowPad}`}>
                      <LanguageBadge language={t.language} />
                    </td>
                    <td className={`pr-4 ${rowPad}`}>
                      <ConfidenceMeter value={t.composite_confidence} policy={policy} />
                    </td>
                    <td className={`tabular-nums ${rowPad} ${ageTone(t.created_at, t.urgency)}`}>
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
