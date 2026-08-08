import evals from "../data/evals.json";

/**
 * The measurement page.
 *
 * Everything here is a build-time import of a real eval report, not a live
 * query: a report describes a run that happened, against a corpus and a
 * threshold that were true at the time. Regenerate with `make ui-evals`.
 *
 * The ordering is deliberate. Auto-reply precision missed its target, and it is
 * the first thing on the page rather than something a reader has to dig for.
 * The whole argument of the project is that the handoff decision is the feature,
 * so a page that led with the flattering numbers would be arguing against
 * itself.
 */

type Sweep = {
  threshold: number;
  auto_reply_precision: number;
  auto_replied: number;
  review_recall: number;
  routing_accuracy: number;
};

const report = evals.report;
const threshold = report.thresholds.auto_reply;

function Stat({
  label,
  value,
  detail,
  tone = "ink",
  target,
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: "ink" | "teal" | "mustard" | "rust";
  target?: string;
}) {
  const color =
    tone === "teal"
      ? "text-teal"
      : tone === "mustard"
        ? "text-mustard"
        : tone === "rust"
          ? "text-rust"
          : "text-ink";
  return (
    <div className="card p-3">
      <div className="eyebrow">{label}</div>
      <div className={`mt-1 text-2xl tabular-nums ${color}`}>{value}</div>
      {detail && <div className="mt-0.5 text-[11px] tabular-nums text-ink-3">{detail}</div>}
      {target && <div className="prose-human mt-1 text-[11px] text-ink-3">{target}</div>}
    </div>
  );
}

/** Bar whose fill is a share of 1.0, used for the per-intent table. */
function Bar({ value, tone }: { value: number; tone: string }) {
  return (
    <span className="inline-block h-[6px] w-16 overflow-hidden rounded-[1px] bg-paper-3 align-middle">
      <span className={`block h-full ${tone}`} style={{ width: `${value * 100}%` }} />
    </span>
  );
}

export default function Evals() {
  const sweep = report.threshold_sweep as Sweep[];
  const runs = evals.runs;
  const ablation = evals.ablation;

  // The two stored runs were measured at different thresholds -- 0.85 and 0.90 --
  // so their headline figures are not a repeatability comparison. Re-reading each
  // run's own sweep at the threshold now in force is the honest way to compare
  // them, and it is what makes the spread a statement about variance rather than
  // about policy.
  const matched = runs
    .map((r) => (r.sweep as Sweep[]).find((s) => s.threshold === threshold))
    .filter((s): s is Sweep => Boolean(s));

  return (
    <div className="space-y-10">
      <header className="space-y-2">
        <h1 className="text-lg font-semibold tracking-tight">Evaluation</h1>
        <p className="prose-human max-w-2xl text-sm text-ink-2">
          Golden set <span className="tabular-nums">{report.golden}</span>,{" "}
          <span className="tabular-nums">{report.tickets}</span> hand-written tickets,
          auto-reply threshold <span className="tabular-nums">{threshold}</span>. These are
          the numbers the design is accountable to, including the one it misses.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="eyebrow">risk metrics</h2>
        <p className="prose-human max-w-2xl text-xs text-ink-2">
          These two lead because they encode the asymmetry. A false auto-reply reaches a
          customer; a missed review is a silent failure. Routing accuracy alone hides both.
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="auto-reply precision"
            value={report.auto_reply_precision.toFixed(3)}
            detail={report.auto_reply_precision_detail}
            tone="rust"
            target="Target was 0.95. Not met — see below."
          />
          <Stat
            label="review recall"
            value={report.review_recall.toFixed(3)}
            detail={report.review_recall_detail}
            tone="teal"
          />
          <Stat
            label="routing accuracy"
            value={report.routing_accuracy.toFixed(3)}
            tone="mustard"
          />
          <Stat
            label="cost per ticket"
            value={`₹${report.cost_inr_per_ticket.toFixed(3)}`}
            detail={`p95 ${(report.latency.p95_ms / 1000).toFixed(1)}s`}
          />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="eyebrow">what the table is not saying on its own</h2>
        <div className="grid gap-3 lg:grid-cols-3">
          <div className="card space-y-1.5 p-3">
            <p className="text-xs font-medium text-rust">The bar is missed, not moved.</p>
            <p className="prose-human text-xs leading-relaxed text-ink-2">
              The design set auto-reply precision at 0.95. The sweep reaches 0.727 at 0.85 and
              0.778 at 0.90, and auto-replies to nothing at 0.95. The threshold was raised from
              0.85 to 0.90 to trade coverage for safety. The target was not lowered to make the
              number look met.
            </p>
          </div>
          <div className="card space-y-1.5 p-3">
            <p className="text-xs font-medium text-mustard">The metric is unstable here.</p>
            <p className="prose-human text-xs leading-relaxed text-ink-2">
              Two runs, re-routed at a matched {threshold} threshold, return{" "}
              <span className="tabular-nums">
                {matched.map((s) => s.auto_reply_precision.toFixed(3)).join(" and ")}
              </span>
              {matched.length === 2 && (
                <>
                  {" "}
                  on{" "}
                  <span className="tabular-nums">
                    {matched.map((s) => s.auto_replied).join(" and ")}
                  </span>{" "}
                  auto-replies
                </>
              )}
              . With a denominator that small, one ticket flipping moves precision ten points.
              Intent accuracy, measured across all{" "}
              <span className="tabular-nums">{report.tickets}</span>, held to three decimals
              across both.
            </p>
          </div>
          <div className="card space-y-1.5 p-3">
            <p className="text-xs font-medium text-mustard">Confidence is overconfident.</p>
            <p className="prose-human text-xs leading-relaxed text-ink-2">
              Every reliability bucket sits below the diagonal. The weights were a guess, and
              two of the three inputs are optimistic by construction. Fitting them against
              outcomes is the obvious next step.
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="eyebrow">component accuracy</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="intent" value={report.intent_accuracy.toFixed(3)} tone="teal" />
          <Stat label="intent macro f1" value={report.intent_macro_f1.toFixed(3)} tone="teal" />
          <Stat
            label="intent · hinglish"
            value={report.intent_accuracy_hinglish.toFixed(3)}
            detail={`english ${report.intent_accuracy_english.toFixed(3)}`}
          />
          <Stat
            label="language"
            value={report.language_accuracy.toFixed(3)}
            target="Correct on all 60 — but only one ticket is Devanagari, so this says little about the script."
            tone="teal"
          />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="eyebrow">calibration</h2>
        <p className="prose-human max-w-2xl text-xs text-ink-2">
          Stated confidence against observed correctness. Bars below the line are
          overconfidence, which is where it is dangerous.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="rule-row text-left">
                <th className="eyebrow py-1.5 pr-4 font-medium">bucket</th>
                <th className="eyebrow py-1.5 pr-4 font-medium">n</th>
                <th className="eyebrow py-1.5 pr-4 font-medium">stated</th>
                <th className="eyebrow py-1.5 pr-4 font-medium">observed</th>
                <th className="eyebrow py-1.5 font-medium">gap</th>
              </tr>
            </thead>
            <tbody>
              {report.reliability.map((b) => {
                const gap = b.observed_correct - b.mean_confidence;
                return (
                  <tr key={b.lower} className="rule-row">
                    <td className="py-1.5 pr-4 tabular-nums text-ink-2">
                      {b.lower.toFixed(1)}–{b.upper.toFixed(1)}
                    </td>
                    <td className="py-1.5 pr-4 tabular-nums text-ink-3">{b.n}</td>
                    <td className="py-1.5 pr-4 tabular-nums">{b.mean_confidence.toFixed(3)}</td>
                    <td className="py-1.5 pr-4 tabular-nums">{b.observed_correct.toFixed(3)}</td>
                    <td className="py-1.5 tabular-nums text-rust">{gap.toFixed(3)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="eyebrow">threshold sweep</h2>
        <p className="prose-human max-w-2xl text-xs text-ink-2">
          Hard rules — P1, weak retrieval, safe fallback — are held fixed; only the composite
          band moves. Raising the threshold buys safety and costs coverage, and shrinks the
          denominator that precision is measured on.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="rule-row text-left">
                <th className="eyebrow py-1.5 pr-4 font-medium">threshold</th>
                <th className="eyebrow py-1.5 pr-4 font-medium">precision</th>
                <th className="eyebrow py-1.5 pr-4 font-medium">auto-replied</th>
                <th className="eyebrow py-1.5 pr-4 font-medium">review recall</th>
                <th className="eyebrow py-1.5 font-medium">routing</th>
              </tr>
            </thead>
            <tbody>
              {sweep.map((s) => (
                <tr
                  key={s.threshold}
                  className={`rule-row ${s.threshold === threshold ? "bg-paper-2" : ""}`}
                >
                  <td className="py-1.5 pr-4 tabular-nums">
                    {s.threshold.toFixed(2)}
                    {s.threshold === threshold && (
                      <span className="ml-2 text-[10px] text-teal">in force</span>
                    )}
                  </td>
                  <td className="py-1.5 pr-4">
                    <span className="mr-2 tabular-nums">
                      {s.auto_reply_precision.toFixed(3)}
                    </span>
                    <Bar value={s.auto_reply_precision} tone="bg-mustard-fill" />
                  </td>
                  <td className="py-1.5 pr-4 tabular-nums text-ink-3">{s.auto_replied}</td>
                  <td className="py-1.5 pr-4">
                    <span className="mr-2 tabular-nums">{s.review_recall.toFixed(3)}</span>
                    <Bar value={s.review_recall} tone="bg-teal-fill" />
                  </td>
                  <td className="py-1.5 tabular-nums text-ink-3">
                    {s.routing_accuracy.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {ablation && (
        <section className="space-y-3">
          <h2 className="eyebrow">does the judge earn its weight?</h2>
          <p className="prose-human max-w-2xl text-xs text-ink-2">
            The composite is re-computed offline under reweighted arms, replaying the recorded
            signals through the real routing policy. Best precision each arm reaches at any
            threshold, counting only arms that answer at least five tickets.{" "}
            <span className="tabular-nums">{ablation.composite_decided}</span> of{" "}
            <span className="tabular-nums">{ablation.tickets}</span> tickets are decided by the
            composite at all; the rest are settled by hard rules in every arm.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(ablation.arms).map(([name, arm]) => (
              <div
                key={name}
                className={`card p-3 ${name === "judge_only" ? "border-teal/50" : ""}`}
              >
                <div className="eyebrow">{name.replace(/_/g, " ")}</div>
                <div className="mt-1 text-xl tabular-nums">
                  {arm.best ? arm.best.auto_reply_precision.toFixed(3) : "—"}
                </div>
                <div className="mt-0.5 text-[11px] tabular-nums text-ink-3">
                  {arm.best
                    ? `at ${arm.best.threshold.toFixed(2)} · ${arm.best.auto_reply_detail}`
                    : "never answers 5+"}
                </div>
                <div className="mt-1.5 text-[11px] tabular-nums text-ink-3">
                  judge {arm.weights.judge} · clf {arm.weights.classifier} · retr{" "}
                  {arm.weights.retrieval}
                </div>
              </div>
            ))}
          </div>
          <p className="prose-human max-w-2xl text-xs leading-relaxed text-ink-2">
            The judge-only arm beats the shipped composite in both runs, which says the guess
            was worse than not guessing: the classifier and retrieval terms dilute the judge
            rather than supplement it. Whether the judge is strictly <em>necessary</em> is not
            settled at this sample size — that arm changes sign between runs.
          </p>
        </section>
      )}

      <footer className="space-y-1 border-t border-rule pt-4">
        <p className="text-[11px] tabular-nums text-ink-3">
          {report.models.classifier} · {report.models.drafter} · {report.models.judge} ·{" "}
          {report.models.embedding}
        </p>
        <p className="text-[11px] text-ink-3">
          source {evals.source} · {report.elapsed_seconds}s ·{" "}
          {report.tickets_with_errors} tickets with node errors
        </p>
      </footer>
    </div>
  );
}
