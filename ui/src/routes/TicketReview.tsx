import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Confidence, IntentBadge, LanguageBadge, RouteBadge, UrgencyBadge } from "../components/Badges";
import { getTicket, submitReview } from "../lib/api";
import { timestamp } from "../lib/format";
import type { ReviewPayload } from "../lib/types";

const SCORE_LABELS: Record<string, string> = {
  groundedness: "Grounded",
  completeness: "Complete",
  tone: "Tone",
};

export default function TicketReview() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const { data, isPending, error } = useQuery({
    queryKey: ["ticket", id],
    queryFn: () => getTicket(id),
  });

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

  if (isPending) return <p className="text-sm text-neutral-500">Loading…</p>;
  if (error) return <p className="text-sm text-red-600">{String(error)}</p>;
  if (!data) return null;

  const cases = data.retrieval?.cases ?? [];
  const cited = new Set(data.draft_citations ?? []);
  const edited = text.trim() !== (data.draft ?? "").trim();
  const settled = data.status === "resolved" || data.status === "escalated";

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm text-neutral-500 underline-offset-2 hover:underline">
        ← queues
      </Link>

      <header className="space-y-2">
        <h1 className="text-xl font-semibold">{data.subject}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <IntentBadge intent={data.classification?.intent ?? null} />
          <UrgencyBadge urgency={data.classification?.urgency ?? null} />
          <LanguageBadge language={data.classification?.language ?? null} />
          <RouteBadge route={data.route} />
          <span className="text-neutral-500">
            confidence <Confidence value={data.composite_confidence} />
          </span>
          <span className="text-neutral-400">{timestamp(data.created_at)}</span>
        </div>
        <p className="whitespace-pre-wrap rounded bg-neutral-50 p-3 text-sm dark:bg-neutral-900">
          {data.body}
        </p>
      </header>

      {data.errors && data.errors.length > 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950">
          <p className="font-medium">This run had errors</p>
          <ul className="mt-1 list-inside list-disc text-xs">
            {data.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Why this route
        </h2>
        <p className="rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
          {data.route_reason ?? "—"}
        </p>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Draft reply
        </h2>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          disabled={settled}
          className="w-full rounded border border-neutral-300 p-3 font-mono text-sm disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-900"
        />
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (optional) — why you approved, edited, or rejected"
          disabled={settled}
          className="mt-2 w-full rounded border border-neutral-300 p-2 text-sm disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-900"
        />

        {settled ? (
          <p className="mt-3 text-sm text-neutral-500">
            Already {data.status}. Reviewed tickets are not re-decided here.
          </p>
        ) : (
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => review.mutate({ action: "approve", note: note || undefined })}
              disabled={review.isPending || edited}
              title={edited ? "The draft has been changed — use Save edit" : undefined}
              className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
            >
              Approve
            </button>
            <button
              onClick={() => review.mutate({ action: "edit", final_text: text, note: note || undefined })}
              disabled={review.isPending || !edited}
              className="rounded border border-neutral-400 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-neutral-600"
            >
              Save edit
            </button>
            <button
              onClick={() => review.mutate({ action: "reject", note: note || undefined })}
              disabled={review.isPending}
              className="rounded border border-red-400 px-3 py-1.5 text-sm text-red-700 disabled:opacity-40 dark:text-red-300"
            >
              Reject
            </button>
          </div>
        )}
        {review.isError && <p className="mt-2 text-sm text-red-600">{String(review.error)}</p>}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Judge
        </h2>
        {data.judge_scores ? (
          <div className="rounded border border-neutral-200 p-3 dark:border-neutral-800">
            <div className="flex gap-6 text-sm">
              {(["groundedness", "completeness", "tone"] as const).map((k) => (
                <div key={k}>
                  <div className="text-xs uppercase tracking-wide text-neutral-500">
                    {SCORE_LABELS[k]}
                  </div>
                  <div className="tabular-nums text-lg">{data.judge_scores![k]}<span className="text-sm text-neutral-400">/5</span></div>
                </div>
              ))}
            </div>
            <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
              {data.judge_scores.notes}
            </p>
          </div>
        ) : (
          <p className="text-sm text-neutral-500">The judge did not score this run.</p>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Evidence {data.retrieval?.weak && <span className="text-amber-600">(weak)</span>}
        </h2>
        {cases.length === 0 && <p className="text-sm text-neutral-500">Nothing was retrieved.</p>}
        <ul className="space-y-1">
          {cases.map((c, i) => {
            const n = i + 1;
            const open = openCase === n;
            return (
              <li key={c.case_id} className="rounded border border-neutral-200 dark:border-neutral-800">
                <button
                  onClick={() => setOpenCase(open ? null : n)}
                  className="flex w-full items-center gap-2 p-2 text-left text-sm"
                >
                  <span className="tabular-nums text-neutral-400">[{n}]</span>
                  {cited.has(n) && (
                    <span className="rounded bg-neutral-900 px-1 text-xs text-white dark:bg-neutral-100 dark:text-neutral-900">
                      cited
                    </span>
                  )}
                  <span className="truncate">{c.customer_text}</span>
                  <span className="ml-auto tabular-nums text-xs text-neutral-400">
                    {c.similarity.toFixed(3)}
                  </span>
                </button>
                {open && (
                  <div className="border-t border-neutral-200 p-3 text-sm dark:border-neutral-800">
                    <p className="whitespace-pre-wrap"><strong>Customer:</strong> {c.customer_text}</p>
                    <p className="mt-2 whitespace-pre-wrap"><strong>Resolution:</strong> {c.resolution_text}</p>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <footer className="flex gap-4 border-t border-neutral-200 pt-4 text-xs text-neutral-500 dark:border-neutral-800">
        {data.latency_ms && (
          <span>
            latency{" "}
            {Object.entries(data.latency_ms).map(([k, v]) => `${k} ${v}ms`).join(" · ")}
          </span>
        )}
        {data.langfuse_trace_id && <span>trace {data.langfuse_trace_id.slice(0, 12)}…</span>}
      </footer>
    </div>
  );
}
