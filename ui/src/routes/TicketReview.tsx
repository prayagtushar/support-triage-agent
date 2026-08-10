import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { IntentBadge, LanguageBadge, RouteBadge, UrgencyBadge } from "../components/Badges";
import { Composite } from "../components/Composite";
import { ConfidenceMeter, ScoreTicks, scoreTone } from "../components/Meter";
import { Pipeline } from "../components/Pipeline";
import { getPolicy, getTicket, submitReview } from "../lib/api";
import { timestamp } from "../lib/format";
import type { ReviewPayload } from "../lib/types";

const SCORE_LABELS = {
  groundedness: "grounded",
  completeness: "complete",
  tone: "tone",
} as const;

function Section({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h2 className="eyebrow">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export default function TicketReview() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const { data, isPending, error } = useQuery({
    queryKey: ["ticket", id],
    queryFn: () => getTicket(id),
  });
  const { data: policy } = useQuery({ queryKey: ["policy"], queryFn: getPolicy });

  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [openCase, setOpenCase] = useState<number | null>(null);

  useEffect(() => {
    if (data?.draft) setText(data.draft);
  }, [data?.draft]);

  const review = useMutation({
    mutationFn: (payload: ReviewPayload) => submitReview(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ticket", id] });
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });

  if (isPending) return <p className="text-sm text-ink-3">Loading…</p>;
  if (error) return <p className="text-sm text-rust">{String(error)}</p>;
  if (!data) return null;

  const cases = data.retrieval?.cases ?? [];
  const cited = new Set(data.draft_citations ?? []);
  const edited = text.trim() !== (data.draft ?? "").trim();
  const settled = data.status === "resolved" || data.status === "escalated";

  return (
    <div className="space-y-8">
      <Link to="/" className="text-xs text-ink-3 underline-offset-2 hover:text-ink hover:underline">
        ← queues
      </Link>

      <header className="space-y-3">
        <h1 className="prose-human text-xl font-semibold tracking-tight">{data.subject}</h1>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <IntentBadge intent={data.classification?.intent ?? null} />
          <UrgencyBadge urgency={data.classification?.urgency ?? null} />
          <LanguageBadge language={data.classification?.language ?? null} />
          <RouteBadge route={data.route} />
          <ConfidenceMeter value={data.composite_confidence} policy={policy} width="w-24" />
          <span className="ml-auto tabular-nums text-ink-3">{timestamp(data.created_at)}</span>
        </div>
        <p className="prose-human rounded-[2px] border-l-2 border-rule-2 bg-paper-2 p-3 text-sm whitespace-pre-wrap">
          {data.body}
        </p>
      </header>

      {data.errors && data.errors.length > 0 && (
        <div className="rounded-[2px] border border-rust/40 bg-rust-bg p-3">
          <p className="text-xs font-medium text-rust">This run had errors</p>
          <ul className="mt-1.5 space-y-1">
            {data.errors.map((e, i) => (
              <li key={i} className="text-[11px] leading-relaxed text-rust/90">
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Left: what a reviewer acts on. Right: what they need to trust it. */}
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <div className="space-y-8">
          {/* No "safe fallback" flag here on purpose: the pipeline computes one
              but agent_runs does not persist it, and route_reason cannot tell it
              apart from weak retrieval. Better to show nothing than to guess. */}
          <Section title="draft reply">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={12}
              disabled={settled}
              aria-label="Draft reply"
              className="w-full rounded-[2px] border border-rule bg-paper-2 p-3 text-sm leading-relaxed disabled:opacity-60"
            />
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Note — why you approved, edited, or rejected"
              disabled={settled}
              className="prose-human mt-2 w-full rounded-[2px] border border-rule bg-paper-2 p-2 text-sm disabled:opacity-60"
            />

            {settled ? (
              <p className="prose-human mt-3 text-sm text-ink-2">
                Already {data.status}. Reviewed tickets are not re-decided here.
              </p>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => review.mutate({ action: "approve", note: note || undefined })}
                  disabled={review.isPending || edited}
                  title={edited ? "The draft has been changed — use Save edit" : undefined}
                  className="rounded-[2px] bg-teal px-3 py-1.5 text-xs font-medium text-paper transition-opacity disabled:opacity-40"
                >
                  Approve
                </button>
                <button
                  onClick={() =>
                    review.mutate({ action: "edit", final_text: text, note: note || undefined })
                  }
                  disabled={review.isPending || !edited}
                  className="rounded-[2px] border border-rule-2 px-3 py-1.5 text-xs text-ink transition-colors hover:border-ink-3 disabled:opacity-40"
                >
                  Save edit
                </button>
                <button
                  onClick={() => review.mutate({ action: "reject", note: note || undefined })}
                  disabled={review.isPending}
                  className="rounded-[2px] border border-rust/50 px-3 py-1.5 text-xs text-rust transition-colors hover:bg-rust-bg disabled:opacity-40"
                >
                  Reject
                </button>
              </div>
            )}
            {review.isError && <p className="mt-2 text-xs text-rust">{String(review.error)}</p>}
          </Section>

          <Section
            title="evidence"
            aside={
              data.retrieval?.weak ? (
                <span className="text-[11px] text-mustard">
                  weak · best similarity {(data.retrieval.best_similarity ?? 0).toFixed(3)}
                </span>
              ) : undefined
            }
          >
            {cases.length === 0 ? (
              <p className="prose-human text-sm text-ink-2">
                Nothing was retrieved, so the draft above is grounded in nothing. The router
                treats that as a hard rule and sends the ticket to a human regardless of score.
              </p>
            ) : (
              <ul className="space-y-1">
                {cases.map((c, i) => {
                  const n = i + 1;
                  const open = openCase === n;
                  return (
                    <li key={c.case_id} className="rounded-[2px] border border-rule bg-paper-2">
                      <button
                        onClick={() => setOpenCase(open ? null : n)}
                        aria-expanded={open}
                        className="flex w-full items-center gap-2 p-2 text-left text-xs"
                      >
                        <span className="tabular-nums text-ink-3">[{n}]</span>
                        {cited.has(n) && (
                          <span className="rounded-[2px] bg-olive-bg px-1 text-[10px] font-medium text-olive">
                            cited
                          </span>
                        )}
                        <span className="prose-human truncate text-ink-2">{c.customer_text}</span>
                        <span className="ml-auto tabular-nums text-ink-3">
                          {c.similarity.toFixed(3)}
                        </span>
                      </button>
                      {open && (
                        <div className="prose-human space-y-2 border-t border-rule p-3 text-xs">
                          <p className="whitespace-pre-wrap">
                            <span className="eyebrow">customer</span>
                            <br />
                            {c.customer_text}
                          </p>
                          <p className="whitespace-pre-wrap">
                            <span className="eyebrow">resolution</span>
                            <br />
                            {c.resolution_text}
                          </p>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>
        </div>

        <aside className="space-y-8">
          <Section title="why this route">
            <p className="prose-human rounded-[2px] bg-paper-2 p-3 text-xs leading-relaxed">
              {data.route_reason ?? "—"}
            </p>
          </Section>

          <Section title="how the score was built">
            <Composite
              policy={policy}
              judge={data.judge_scores}
              classification={data.classification}
              retrieval={data.retrieval}
              composite={data.composite_confidence}
            />
          </Section>

          <Section title="judge">
            {data.judge_scores ? (
              <div className="space-y-2">
                {(["groundedness", "completeness", "tone"] as const).map((k) => (
                  <div key={k} className="flex items-center justify-between gap-3">
                    <span className="text-xs text-ink-2">{SCORE_LABELS[k]}</span>
                    <span className="flex items-center gap-2">
                      <ScoreTicks
                        value={data.judge_scores![k]}
                        tone={scoreTone(data.judge_scores![k])}
                      />
                      <span className="tabular-nums text-xs text-ink-3">
                        {data.judge_scores![k]}/5
                      </span>
                    </span>
                  </div>
                ))}
                <p className="prose-human border-t border-rule pt-2 text-xs leading-relaxed text-ink-2">
                  {data.judge_scores.notes}
                </p>
              </div>
            ) : (
              <p className="prose-human text-xs text-ink-2">The judge did not score this run.</p>
            )}
          </Section>

          {data.classification?.rationale && (
            <Section title="classifier reasoning">
              <p className="prose-human text-xs leading-relaxed text-ink-2">
                {data.classification.rationale}
              </p>
              <p className="mt-2 text-[11px] text-ink-3">
                self-reported confidence {data.classification.confidence.toFixed(2)} · sentiment{" "}
                {data.classification.sentiment}
              </p>
            </Section>
          )}

        </aside>
      </div>

      {/* Full width, below both columns: the node list is wide content and was
          being crushed into the sidebar. */}
      <Section
        title="pipeline"
        aside={
          data.langfuse_trace_id ? (
            <span className="text-[11px] text-ink-3">
              trace {data.langfuse_trace_id.slice(0, 12)}…
            </span>
          ) : undefined
        }
      >
        <Pipeline latency={data.latency_ms} usage={data.token_usage} errors={data.errors} />
      </Section>
    </div>
  );
}
