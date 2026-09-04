import { useState } from "react";

import evals from "../data/evals.json";
import { REPO_URL } from "../lib/links";
import { usePolicy } from "../lib/usePolicy";

const report = evals.report;

/** Indicative only, and stated as such wherever a dollar figure appears. */
const INR_PER_USD = 83;

const SETUP = `git clone ${REPO_URL}
cd support-triage-agent
cp api/.env.example api/.env   # three provider keys
make demo                      # database, corpus, embeddings, seeded queues`;

function Money({ inr }: { inr: number }) {
  return (
    <span className="tabular-nums">
      ₹{inr.toLocaleString("en-IN", { maximumFractionDigits: 0 })}{" "}
      <span className="text-ink-3">/ ${(inr / INR_PER_USD).toFixed(0)}</span>
    </span>
  );
}

/**
 * Volume in, spend and deflection out, from the measured per-ticket cost and the share
 * this corpus actually auto-replied at the threshold in force. Both of those are
 * corpus-specific, so the page says so rather than presenting them as a quote.
 */
function Calculator() {
  const [monthly, setMonthly] = useState(2000);
  const [minutes, setMinutes] = useState(6);

  const atThreshold = report.threshold_sweep.find((s) => s.threshold === report.thresholds.auto_reply);
  const autoShare = (atThreshold?.auto_replied ?? 0) / report.tickets;

  const spend = monthly * report.cost_inr_per_ticket;
  const autoReplied = Math.round(monthly * autoShare);
  const hours = (autoReplied * minutes) / 60;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4">
        <label className="space-y-1">
          <span className="eyebrow block">tickets a month</span>
          <input
            type="number"
            min={0}
            step={100}
            value={monthly}
            onChange={(e) => setMonthly(Math.max(0, Number(e.target.value)))}
            className="w-32 rounded-[2px] border border-rule bg-paper-2 px-2 py-1.5 text-sm tabular-nums"
          />
        </label>
        <label className="space-y-1">
          <span className="eyebrow block">minutes an agent spends on one</span>
          <input
            type="number"
            min={0}
            step={1}
            value={minutes}
            onChange={(e) => setMinutes(Math.max(0, Number(e.target.value)))}
            className="w-32 rounded-[2px] border border-rule bg-paper-2 px-2 py-1.5 text-sm tabular-nums"
          />
        </label>
      </div>

      <dl className="grid gap-3 sm:grid-cols-3">
        <div className="card p-3">
          <dt className="eyebrow">model spend</dt>
          <dd className="mt-1 text-2xl">
            <Money inr={spend} />
          </dd>
          <dd className="mt-0.5 text-[11px] text-ink-3">
            at ₹{report.cost_inr_per_ticket.toFixed(3)} a ticket, measured
          </dd>
        </div>
        <div className="card p-3">
          <dt className="eyebrow">answered without a human</dt>
          <dd className="mt-1 text-2xl tabular-nums">{autoReplied.toLocaleString("en-IN")}</dd>
          <dd className="mt-0.5 text-[11px] text-ink-3">
            {(autoShare * 100).toFixed(0)}% on this corpus at {report.thresholds.auto_reply}
          </dd>
        </div>
        <div className="card p-3">
          <dt className="eyebrow">agent hours freed</dt>
          <dd className="mt-1 text-2xl tabular-nums">{hours.toFixed(0)}</dd>
          <dd className="mt-0.5 text-[11px] text-ink-3">if every auto-reply lands</dd>
        </div>
      </dl>

      <p className="prose-human max-w-2xl text-xs leading-relaxed text-ink-2">
        This corpus belongs to a consumer e-commerce app. Orders, refunds, billing, account access,
        with app bug reports and feature requests on top. The deflection figure assumes your
        tickets behave like it, and they will not.
        It also assumes every auto-reply is a good one, which on the measured numbers is true{" "}
        {(report.auto_reply_precision * 100).toFixed(0)}% of the time, below the 95% this system
        was designed against. Treat the spend column as reliable and the other two as an upper
        bound until you have run your own tickets through it.
      </p>
    </div>
  );
}

/** Keeps the trailing comments in a column; the values are 0.4 and 0.55 and 0.9. */
function pad(value: number): string {
  return String(value).padEnd(6);
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="rule-row flex gap-4 py-3 last:border-0">
      <span className="tabular-nums text-ink-3">{n}</span>
      <div className="space-y-1">
        <p className="text-sm">{title}</p>
        <p className="prose-human text-xs leading-relaxed text-ink-2">{children}</p>
      </div>
    </li>
  );
}

export default function RunIt() {
  const policy = usePolicy();

  return (
    <div className="max-w-3xl space-y-10">
      <header className="space-y-2">
        <h1 className="text-lg font-semibold tracking-tight">Quickstart</h1>
        <p className="prose-human text-sm text-ink-2">
          Everything here is MIT licensed and runs on the free tier of three services. What
          follows is what it costs, where it sits in an existing support stack, and what you
          would be signing up to maintain.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="eyebrow">what it would cost you</h2>
        <Calculator />
      </section>

      <section className="space-y-3">
        <h2 className="eyebrow">where it sits</h2>
        <p className="prose-human max-w-2xl text-sm text-ink-2">
          The agent is an HTTP service, not a helpdesk. It takes a ticket, returns a route and a
          draft, and leaves delivery to whatever you already run.
        </p>
        <pre className="overflow-x-auto rounded-[2px] border border-rule bg-paper-2 p-3 text-[11px] leading-relaxed">
{`  your helpdesk           this service              your helpdesk
  (Zendesk, Intercom,     POST /tickets             auto-reply  -> send
   Freshdesk, plain  ->   classify, retrieve,  ->   review      -> agent queue
   email)                 draft, judge, route       escalate    -> on-call`}
        </pre>
        <p className="prose-human max-w-2xl text-xs leading-relaxed text-ink-2">
          One webhook in and one branch out. Nothing in the pipeline knows which helpdesk it is
          talking to, and the routing decision is deterministic code you can read in a single
          file.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="eyebrow">running it</h2>
        <pre className="overflow-x-auto rounded-[2px] border border-rule bg-paper-2 p-3 text-xs leading-relaxed">
          {SETUP}
        </pre>
        <ol>
          <Step n={1} title="Bring your own cases">
            Retrieval grounds every draft in your resolved tickets. Load them in place of the
            public corpus, or the drafter will cite someone else's answers at your customers.
          </Step>
          <Step n={2} title="Retune the thresholds against your own data">
            The numbers below were fitted to this corpus. The eval suite,{" "}
            <code className="text-ink-2">make eval</code>,{" "}
            <code className="text-ink-2">make calibrate</code>,{" "}
            <code className="text-ink-2">make ablate</code>, is the part worth keeping.
          </Step>
          <Step n={3} title="Redact before egress if your tickets are real">
            Every ticket body is sent to three third-party providers. This corpus is public and
            synthetic; yours will not be.
          </Step>
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="eyebrow">the policy in force right now</h2>
        <p className="prose-human max-w-2xl text-sm text-ink-2">
          Read live from <code>GET /policy</code>, which is the same source the meters on every
          other page draw against. Changing any of it is a config change, not a code change.
        </p>
        {policy ? (
          <pre className="overflow-x-auto rounded-[2px] border border-rule bg-paper-2 p-3 text-xs leading-relaxed">
{`domain: ${policy.domain}   # who the classifier and drafter think they work for

thresholds:
  auto_reply:            ${pad(policy.thresholds.auto_reply)}# answer without a human above this
  review:                ${pad(policy.thresholds.review)}# below this a human owns it outright
  weak_retrieval_floor:  ${pad(policy.thresholds.weak_retrieval_floor)}# cosine below this counts as no evidence

composite_weights:       # what the router's confidence is made of
  judge:      ${policy.composite_weights.judge}
  classifier: ${policy.composite_weights.classifier}
  retrieval:  ${policy.composite_weights.retrieval}

models:                  # the judge must not share a vendor with the drafter
  classifier: ${policy.models.classifier}
  drafter:    ${policy.models.drafter}
  judge:      ${policy.models.judge}`}
          </pre>
        ) : (
          <p className="text-xs text-ink-3">Loading the live policy…</p>
        )}
        <p className="prose-human max-w-2xl text-xs leading-relaxed text-ink-2">
          Those weights were a guess and the ablation says so: judging on the judge alone scores
          better than the shipped composite. They have not been changed because at 60 tickets
          that result flips sign between runs, and retuning on noise is how a policy gets worse.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="eyebrow">before you commit to it</h2>
        <p className="prose-human max-w-2xl text-sm text-ink-2">
          Auto-reply precision on this corpus is {report.auto_reply_precision.toFixed(2)} against
          a target of 0.95, so auto-reply is not safe to enable here at the standard it was
          designed for. The failure analysis says which component owns each miss.
        </p>
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="text-teal hover:underline">
            source →
          </a>
          <a
            href={`${REPO_URL}/blob/main/docs/failure_analysis.md`}
            target="_blank"
            rel="noreferrer"
            className="text-teal hover:underline"
          >
            failure analysis →
          </a>
          <a
            href={`${REPO_URL}/blob/main/docs/DEPLOY.md`}
            target="_blank"
            rel="noreferrer"
            className="text-teal hover:underline"
          >
            deployment runbook →
          </a>
        </p>
      </section>
    </div>
  );
}
