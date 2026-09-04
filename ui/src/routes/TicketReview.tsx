import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ErrorNote, Skeleton } from "../components/Async";
import { IntentBadge, LanguageBadge, RouteBadge, UrgencyBadge } from "../components/Badges";
import { Composite } from "../components/Composite";
import { Diff } from "../components/Diff";
import { ConfidenceMeter, ScoreTicks, scoreTone } from "../components/Meter";
import { Pipeline } from "../components/Pipeline";
import { getTicket, listTickets, submitReview } from "../lib/api";
import { reviewToast, useToast } from "../components/Toast";
import { useDomain, useLanguage, withDomain } from "../lib/domain";
import { timestamp } from "../lib/format";
import type { RejectReason, ReviewPayload, TicketStatus } from "../lib/types";
import { useHotkeys } from "../lib/useHotkeys";
import { usePolicy } from "../lib/usePolicy";

const SCORE_LABELS = {
  groundedness: "grounded",
  completeness: "complete",
  tone: "tone",
} as const;

/** Free text records what one reviewer thought; these are what the eval suite can count. */
const REJECT_REASONS: { key: RejectReason; label: string; hint: string }[] = [
  { key: "hallucinated", label: "hallucinated", hint: "Asserted something no cited case supports" },
  { key: "wrong_intent", label: "wrong intent", hint: "Classified as the wrong kind of ticket" },
  { key: "wrong_tone", label: "wrong tone", hint: "Accurate, but not sendable as written" },
  { key: "missing_info", label: "missing info", hint: "Correct so far as it goes, does not answer" },
  {
    key: "not_answerable",
    label: "not answerable",
    hint: "No draft could be right; needs a human with access",
  },
  { key: "other", label: "other", hint: "Something else — say what in the note" },
];

const SHORTCUTS = [
  ["a", "approve"],
  ["e", "save edit"],
  ["r", "reject"],
  ["j / k", "next / previous in lane"],
  ["?", "this list"],
];

function Section({
  title,
  aside,
  below,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  below?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h2 className="eyebrow">{title}</h2>
        {aside}
      </div>
      {children}
      {below}
    </section>
  );
}

export default function TicketReview() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isPending, error } = useQuery({
    queryKey: ["ticket", id],
    queryFn: () => getTicket(id),
  });
  const policy = usePolicy();

  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [openCase, setOpenCase] = useState<number | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [showKeys, setShowKeys] = useState(false);

  useEffect(() => {
    if (data?.draft) setText(data.draft);
  }, [data?.draft]);

  // The lane this ticket sits in, so j/k and auto-advance move through actual neighbours.
  // Scoped to the TICKET's desk rather than the one being browsed: a ticket reached by
  // link can belong to another desk, and without this the lane silently mixed them, so
  // j/k walked from a refund into a laptop that would not charge. The desk is in the
  // query key too, or this cache entry collides with the queue's own list.
  // The language filter is in here too: j/k should walk the list the reviewer is
  // actually looking at, not a longer one they filtered away.
  const { lang } = useLanguage();
  const lane = useQuery({
    queryKey: ["tickets", data?.status as TicketStatus, data?.domain_id, lang],
    queryFn: () => listTickets(data!.status, data!.domain_id, lang),
    enabled: Boolean(data?.status && data?.domain_id),
  });

  const siblings = lane.data?.tickets ?? [];
  const position = siblings.findIndex((t) => t.id === id);
  const next = position >= 0 ? siblings[position + 1] : undefined;
  const previous = position > 0 ? siblings[position - 1] : undefined;

  const toast = useToast();
  const { id: domainId, domains } = useDomain();
  const ticketDomain = domains.find((d) => d.id === data?.domain_id);

  const review = useMutation({
    mutationFn: (payload: ReviewPayload) => submitReview(id, payload),
    onSuccess: (_result, payload) => {
      queryClient.invalidateQueries({ queryKey: ["ticket", id] });
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["audit"] });
      // Acting advances, so the confirmation has to outlive the screen it happened on.
      toast(reviewToast(payload.action, next?.id));
      const desk = data?.domain_id ?? domainId;
      navigate(next ? withDomain(`/tickets/${next.id}`, desk) : withDomain("/", desk));
    },
    onError: (err) => toast(err instanceof Error ? err.message : "That did not save.", "bad"),
  });

  const edited = text.trim() !== (data?.draft ?? "").trim();
  const settled = data?.status === "resolved" || data?.status === "escalated";
  const mine = data?.reviewable ?? false;
  const busy = review.isPending;

  const approve = () => review.mutate({ action: "approve", note: note || undefined });
  const saveEdit = () =>
    review.mutate({ action: "edit", final_text: text, note: note || undefined });
  const reject = (reason: RejectReason) =>
    review.mutate({ action: "reject", reason, note: note || undefined });

  useHotkeys({
    a: mine && !settled && !busy && !edited ? approve : undefined,
    e: mine && !settled && !busy && edited ? saveEdit : undefined,
    r: mine && !settled && !busy ? () => setRejecting(true) : undefined,
    j: next ? () => navigate(`/tickets/${next.id}`) : undefined,
    k: previous ? () => navigate(`/tickets/${previous.id}`) : undefined,
    "?": () => setShowKeys((v) => !v),
    Escape: () => {
      setRejecting(false);
      setShowKeys(false);
    },
  });

  if (isPending) return <Skeleton rows={8} />;
  if (error) return <ErrorNote error={error} what="this ticket" />;
  if (!data) return null;

  const cases = data.retrieval?.cases ?? [];
  const cited = new Set(data.draft_citations ?? []);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to={withDomain("/", data.domain_id)}
          className="text-xs text-ink-3 underline-offset-2 hover:text-ink hover:underline"
        >
          ← queues
        </Link>
        {position >= 0 && (
          <span className="flex items-center gap-3 text-[11px] text-ink-3">
            <span className="tabular-nums">
              {position + 1} of {siblings.length} in this lane
            </span>
            <button
              onClick={() => setShowKeys((v) => !v)}
              aria-expanded={showKeys}
              className="underline-offset-2 hover:text-ink hover:underline"
            >
              shortcuts
            </button>
          </span>
        )}
      </div>

      {/* A ticket reached by link can belong to another desk, and every other piece of
          chrome names the desk being browsed. Without this the page reads as an
          e-commerce ticket about a laptop that will not charge. */}
      {domainId && data.domain_id !== domainId && (
        <div
          role="status"
          className="rounded-[2px] border border-mustard/40 bg-mustard-bg px-3 py-2 text-xs text-mustard"
        >
          <span className="font-medium">Another desk.</span>{" "}
          <span className="prose-human">
            This ticket belongs to {ticketDomain?.name ?? data.domain_id}, not the desk you
            are browsing. Its evidence, taxonomy and neighbours are that desk's.
          </span>
        </div>
      )}

      {showKeys && (
        <dl className="grid gap-x-6 gap-y-1 rounded-[2px] border border-rule bg-paper-2 p-3 text-[11px] sm:grid-cols-2">
          {SHORTCUTS.map(([key, what]) => (
            <div key={key} className="flex items-baseline gap-2">
              <dt className="rounded-[2px] bg-paper-3 px-1.5 py-0.5 text-ink-2">{key}</dt>
              <dd className="text-ink-3">{what}</dd>
            </div>
          ))}
        </dl>
      )}

      <header className="space-y-3">
        <h1 className="prose-human text-xl font-semibold tracking-tight">{data.subject}</h1>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <IntentBadge intent={data.classification?.intent ?? null} />
          <UrgencyBadge urgency={data.classification?.urgency ?? null} />
          <LanguageBadge language={data.classification?.language ?? null} />
          <RouteBadge route={data.route} />
          <ConfidenceMeter value={data.composite_confidence} policy={policy} width="w-24" />
          <span className="tabular-nums text-ink-3 sm:ml-auto">{timestamp(data.created_at)}</span>
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
          {/* No safe-fallback flag: agent_runs never persists it, and route_reason cannot tell. */}
          <Section
            title="draft reply"
            aside={
              edited ? (
                <button
                  onClick={() => setShowDiff((v) => !v)}
                  aria-expanded={showDiff}
                  className="text-[11px] text-ink-3 underline-offset-2 hover:text-ink hover:underline"
                >
                  {showDiff ? "hide what changed" : "what changed"}
                </button>
              ) : undefined
            }
          >
            {showDiff && edited && (
              <div className="mb-2">
                <Diff before={data.draft ?? ""} after={text} />
              </div>
            )}

            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={12}
              disabled={settled || !mine}
              aria-label="Draft reply"
              className="w-full rounded-[2px] border border-rule bg-paper-2 p-3 text-sm leading-relaxed disabled:opacity-60"
            />
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Note — why you approved, edited, or rejected"
              disabled={settled || !mine}
              className="prose-human mt-2 w-full rounded-[2px] border border-rule bg-paper-2 p-2 text-sm disabled:opacity-60"
            />

            {settled ? (
              <p className="prose-human mt-3 text-sm text-ink-2">
                Already {data.status}. Reviewed tickets are not re-decided here.
              </p>
            ) : !mine ? (
              <p className="prose-human mt-3 rounded-[2px] border border-rule bg-paper-2 p-3 text-sm text-ink-2">
                This one is from the seeded corpus, so it stays where it is and the next
                visitor finds a queue with something in it. {" "}
                <Link to="/submit" className="text-teal underline-offset-2 hover:underline">
                  Send your own ticket
                </Link>{" "}
                and you can approve, edit or reject the reply it drafts for you.
              </p>
            ) : rejecting ? (
              <div className="mt-3 space-y-2 rounded-[2px] border border-rust/40 bg-rust-bg p-3">
                <p className="prose-human text-xs text-rust">
                  What was wrong with it? A reject without this is a comment; with it, it is a
                  labelled example the golden set does not have yet.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {REJECT_REASONS.map((r) => (
                    <button
                      key={r.key}
                      onClick={() => reject(r.key)}
                      disabled={busy}
                      title={r.hint}
                      className="rounded-[2px] border border-rust/50 bg-paper px-2 py-1 text-[11px] text-rust transition-colors hover:bg-rust-bg disabled:opacity-40"
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setRejecting(false)}
                  className="text-[11px] text-ink-3 underline-offset-2 hover:text-ink hover:underline"
                >
                  cancel
                </button>
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={approve}
                  disabled={busy || edited}
                  title={edited ? "The draft has been changed — use Save edit" : "a"}
                  className="rounded-[2px] bg-teal px-3 py-1.5 text-xs font-medium text-paper transition-opacity disabled:opacity-40"
                >
                  Approve
                </button>
                <button
                  onClick={saveEdit}
                  disabled={busy || !edited}
                  title="e"
                  className="rounded-[2px] border border-rule-2 px-3 py-1.5 text-xs text-ink transition-colors hover:border-ink-3 disabled:opacity-40"
                >
                  Save edit
                </button>
                <button
                  onClick={() => setRejecting(true)}
                  disabled={busy}
                  title="r"
                  className="rounded-[2px] border border-rust/50 px-3 py-1.5 text-xs text-rust transition-colors hover:bg-rust-bg disabled:opacity-40"
                >
                  Reject
                </button>
              </div>
            )}
            {review.isError && (
              <div className="mt-2">
                <ErrorNote error={review.error} what="that decision — it was not recorded" />
              </div>
            )}
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
            below={
              data.retrieval?.synthetic_only ? (
                <p className="prose-human mt-2 rounded-[2px] border border-mustard/40 bg-mustard-bg p-2 text-xs leading-relaxed text-mustard">
                  Every case cited here was generated, not resolved by a person. Two of the
                  eight intents have no real cases in the corpus, so a draft for one of them is
                  machine text grounded in machine text. Judge it accordingly.
                </p>
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
                        {c.source === "synthetic" && (
                          <span className="rounded-[2px] bg-mustard-bg px-1 text-[10px] font-medium text-mustard">
                            generated
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

      {/* Full width below both columns: the node list was being crushed in the sidebar. */}
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
