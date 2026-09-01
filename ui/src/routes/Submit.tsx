import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { IntentBadge, LanguageBadge, UrgencyBadge } from "../components/Badges";
import { ErrorNote } from "../components/Async";
import { createTicket, getProgress, getTicket } from "../lib/api";
import type { TicketProgress } from "../lib/types";

/** Mirrors TicketIn on the server, so bad input fails here instead of as a 422. */
const MAX_SUBJECT = 500;
const MAX_BODY = 20_000;

const STAGES = [
  { key: "classify", label: "Reading your message" },
  { key: "retrieve", label: "Looking for similar cases" },
  { key: "draft", label: "Writing a reply" },
  { key: "score", label: "Checking the reply" },
  { key: "route", label: "Deciding who handles it" },
] as const;

/** Tickets a visitor can send without having to invent a support problem. */
const EXAMPLES = [
  {
    label: "double charge",
    subject: "Charged twice for my order",
    body: "I was billed Rs 499 twice on the 3rd for my monthly plan, but only one subscription is active. Can you check what happened?",
  },
  {
    label: "hinglish",
    subject: "Refund nahi aaya",
    body: "Maine 2 hafte pehle jacket return kiya tha, pickup bhi ho gaya, lekin refund abhi tak nahi aaya. Please check karke batao kab tak aayega.",
  },
  {
    label: "nothing in the corpus",
    subject: "Does your API support webhooks for ticket events?",
    body: "We want to sync ticket status into our own system. Is there a webhook or do we have to poll? Looking for docs on the payload shape.",
  },
] as const;

function Stages({ progress }: { progress: TicketProgress | undefined }) {
  if (progress && !progress.progress_available) {
    return (
      <p className="prose-human text-sm text-ink-2">
        Working on it. This takes about 40 seconds — the reply is written and then graded by a
        second model before anyone sees it.
      </p>
    );
  }

  const done = new Set(progress?.completed ?? []);
  const skipped = new Set(progress?.skipped ?? []);
  const next = STAGES.find((s) => !done.has(s.key) && !skipped.has(s.key));

  return (
    <ol className="space-y-0">
      {STAGES.map((stage) => {
        const isDone = done.has(stage.key);
        const isSkipped = skipped.has(stage.key);
        const isCurrent = next?.key === stage.key;
        return (
          <li
            key={stage.key}
            className="rule-row flex items-center gap-3 py-2 text-sm last:border-0"
          >
            <span
              aria-hidden
              className={`h-1.5 w-1.5 rounded-full ${
                isDone
                  ? "bg-teal"
                  : isSkipped
                    ? "bg-paper-3"
                    : isCurrent
                      ? "animate-pulse bg-mustard"
                      : "bg-paper-3"
              }`}
            />
            <span
              className={
                isDone ? "text-ink" : isSkipped ? "text-ink-3 line-through" : "text-ink-3"
              }
            >
              {stage.label}
            </span>
            {stage.key === "classify" && progress?.classification && (
              <span className="ml-auto flex gap-1.5">
                <IntentBadge intent={progress.classification.intent} />
                <UrgencyBadge urgency={progress.classification.urgency} />
                <LanguageBadge language={progress.classification.language} />
              </span>
            )}
            {stage.key === "retrieve" && isDone && (
              <span className="ml-auto tabular-nums text-xs text-ink-3">
                {progress?.retrieved_count ?? 0} cases
              </span>
            )}
            {isSkipped && (
              <span className="ml-auto text-xs text-ink-3">
                skipped — nothing to work from
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export default function Submit() {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [ticketId, setTicketId] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () => createTicket(subject.trim(), body.trim()),
    onSuccess: (res) => setTicketId(res.ticket_id),
  });

  // Stop once status leaves 'received': that is set after the run row is written.
  const settled = (p: TicketProgress | undefined) => Boolean(p && p.status !== "received");

  const progress = useQuery({
    queryKey: ["progress", ticketId],
    queryFn: () => getProgress(ticketId!),
    enabled: Boolean(ticketId),
    refetchInterval: (q) => (settled(q.state.data) ? false : 3000),
  });

  const finished = settled(progress.data);

  const result = useQuery({
    queryKey: ["ticket", ticketId],
    queryFn: () => getTicket(ticketId!),
    enabled: Boolean(ticketId) && finished,
  });

  if (ticketId) {
    return (
      <div className="max-w-2xl space-y-6">
        <h1 className="text-lg font-semibold tracking-tight">
          {finished ? "Here's what happened" : "Thanks — we have your message"}
        </h1>

        <div className="card p-4">
          <Stages progress={progress.data} />
        </div>

        {finished && result.data && (
          <div className="space-y-4">
            <p className="prose-human text-sm text-ink-2">
              {result.data.route === "auto_reply"
                ? "The agent was confident enough to answer this without a human."
                : result.data.route === "escalate"
                  ? "This one goes straight to a person — policy says it should not be answered automatically."
                  : "A human will review the reply before you hear back."}
            </p>

            {result.data.draft && (
              <div className="card p-3">
                <div className="eyebrow mb-1.5">the reply it drafted</div>
                <p className="prose-human text-sm leading-relaxed whitespace-pre-wrap">
                  {result.data.draft}
                </p>
              </div>
            )}

            <Link
              to={`/tickets/${ticketId}`}
              className="inline-block rounded-[2px] border border-rule-2 px-3 py-1.5 text-xs transition-colors hover:border-ink-3"
            >
              Review it the way an agent would →
            </Link>
          </div>
        )}

        {!finished && (
          <p className="text-xs tabular-nums text-ink-3">
            ticket {ticketId.slice(0, 8)} · about 40 seconds
          </p>
        )}

        <button
          onClick={() => {
            setTicketId(null);
            setSubject("");
            setBody("");
          }}
          className="text-xs text-ink-3 underline-offset-2 hover:text-ink hover:underline"
        >
          Send another
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-lg font-semibold tracking-tight">Contact support</h1>
        <p className="prose-human text-sm text-ink-2">
          Send a ticket the way a customer would — your own, ideally, rather than one of the
          examples. It runs through the real pipeline, so it takes about 40 seconds and you can
          watch each step.
        </p>
        <p className="prose-human text-xs text-ink-3">
          No account and no key. When it finishes you can approve, edit or reject the reply it
          drafted for you, the same way a support agent would.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <span className="eyebrow">try one</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            onClick={() => {
              setSubject(ex.subject);
              setBody(ex.body);
            }}
            className="rounded-[2px] border border-rule px-2 py-1 text-[11px] text-ink-2 transition-colors hover:border-rule-2 hover:text-ink"
          >
            {ex.label}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit.mutate();
        }}
        className="space-y-4"
      >
        <label className="block space-y-1.5">
          <span className="eyebrow">subject</span>
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value.slice(0, MAX_SUBJECT))}
            required
            className="prose-human w-full rounded-[2px] border border-rule bg-paper-2 p-2 text-sm"
          />
        </label>

        <label className="block space-y-1.5">
          <span className="eyebrow">how can we help?</span>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value.slice(0, MAX_BODY))}
            required
            rows={7}
            className="prose-human w-full rounded-[2px] border border-rule bg-paper-2 p-3 text-sm leading-relaxed"
          />
        </label>

        {submit.isError && (
          <ErrorNote error={submit.error} what="that ticket — it was not sent" />
        )}

        <button
          type="submit"
          disabled={submit.isPending || !subject.trim() || !body.trim()}
          className="rounded-[2px] bg-teal px-4 py-2 text-xs font-medium text-paper transition-opacity disabled:opacity-40"
        >
          {submit.isPending ? "Sending…" : "Send message"}
        </button>
      </form>
    </div>
  );
}
