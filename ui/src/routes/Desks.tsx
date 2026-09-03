import { Link } from "react-router-dom";

import { ErrorNote, Skeleton } from "../components/Async";
import { useDomain, useDomains, withDomain } from "../lib/domain";
import type { DomainSummary } from "../lib/types";

/**
 * Every desk side by side.
 *
 * The switcher moves you between desks; this says which one is worth opening. Volume and
 * waiting count are the operational read; provenance and case count are the epistemic
 * one, and both belong on the same card because a full queue on a generated corpus looks
 * exactly like a full queue on a real one.
 */
function Card({ desk, current }: { desk: DomainSummary; current: string }) {
  const lanes = [
    { label: "needs review", n: desk.in_review, dot: "bg-mustard-fill", path: "/" },
    { label: "escalated", n: desk.escalated, dot: "bg-rust-fill", path: "/escalated" },
    { label: "auto-replied", n: desk.auto_replied, dot: "bg-teal-fill", path: "/auto-replied" },
  ];

  return (
    <article
      className={`rounded-[2px] border p-4 transition-colors ${
        desk.id === current ? "border-rule-2 bg-paper-2" : "border-rule bg-paper hover:border-rule-2"
      }`}
    >
      <header className="mb-3 flex flex-wrap items-baseline gap-2">
        <h2 className="text-sm font-semibold tracking-tight">{desk.name}</h2>
        {desk.provenance === "synthetic" ? (
          <span className="rounded-[1px] bg-mustard-bg px-1.5 py-px text-[10px] text-mustard">
            generated corpus
          </span>
        ) : (
          <span className="rounded-[1px] bg-teal-bg px-1.5 py-px text-[10px] text-teal">
            real corpus
          </span>
        )}
        {!desk.ready && (
          <span className="rounded-[1px] bg-rust-bg px-1.5 py-px text-[10px] text-rust">
            no evidence
          </span>
        )}
      </header>

      <p className="prose-human mb-4 text-xs text-ink-2">Tickets are {desk.description}'s.</p>

      <dl className="mb-4 grid grid-cols-3 gap-3 border-y border-rule py-3">
        {lanes.map((l) => (
          <div key={l.label}>
            <dt className="flex items-center gap-1.5 text-[11px] text-ink-3">
              <span className={`h-1.5 w-1.5 rounded-full ${l.dot}`} aria-hidden />
              {l.label}
            </dt>
            <dd className="mt-0.5 text-lg tabular-nums text-ink">{l.n}</dd>
          </div>
        ))}
      </dl>

      <dl className="mb-4 space-y-1 text-[11px]">
        <div className="flex justify-between">
          <dt className="text-ink-3">resolved cases</dt>
          <dd className="tabular-nums text-ink-2">
            {desk.cases.toLocaleString()}
            {desk.cases > 0 && desk.synthetic_cases > 0 && (
              <span className="text-ink-3">
                {" "}
                ({Math.round((desk.synthetic_cases / desk.cases) * 100)}% generated)
              </span>
            )}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-ink-3">intents</dt>
          <dd className="tabular-nums text-ink-2">{desk.intents.length}</dd>
        </div>
      </dl>

      <p className="mb-4 flex flex-wrap gap-1">
        {desk.intents.map((i) => (
          <span key={i} className="rounded-[1px] bg-paper-3 px-1.5 py-px text-[10px] text-ink-2">
            {desk.intent_labels[i] ?? i}
          </span>
        ))}
      </p>

      <Link
        to={withDomain("/", desk.id)}
        className="inline-block rounded-[2px] bg-teal px-3 py-1.5 text-xs font-medium text-paper transition-opacity hover:opacity-90"
      >
        Open {desk.name}
      </Link>
    </article>
  );
}

export default function Desks() {
  const { data, error, isPending } = useDomains();
  const { id } = useDomain();

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-lg font-semibold tracking-tight">Desks</h1>
        <p className="prose-human max-w-2xl text-sm text-ink-2">
          One agent, one routing policy, one review queue, pointed at different businesses.
          Each desk carries its own resolved cases, its own intent taxonomy and its own
          worked examples, and retrieval never crosses between them: a laptop that will not
          boot answered from a refund policy is worse than no evidence at all.
        </p>
      </header>

      {isPending && <Skeleton rows={2} />}
      {error && <ErrorNote error={error} what="the desks" />}

      <div className="grid gap-4 md:grid-cols-2">
        {data?.domains.map((d) => (
          <Card key={d.id} desk={d} current={id} />
        ))}
      </div>
    </div>
  );
}
