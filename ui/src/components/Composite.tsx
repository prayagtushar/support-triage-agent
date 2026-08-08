import type { JudgeScores, Policy, Retrieval, Classification } from "../lib/types";

/**
 * The composite confidence, shown as the arithmetic that produced it.
 *
 * `route_reason` already says "composite 0.78 in the review band", which tells a
 * reviewer the outcome but not why. Breaking the number into its three weighted
 * parts shows which signal actually moved the decision -- and makes a finding
 * from the judge ablation visible without having to read it: the classifier
 * term sits near 0.95 on almost every ticket, so it contributes weight without
 * contributing information, and the retrieval term is a proxy for relevance
 * rather than a measure of whether the case answers the question.
 *
 * Weights come from /policy. Hardcoding 0.5/0.3/0.2 here would make this panel
 * lie the moment the policy was retuned, which is the change this project
 * expects to make next.
 */
export function Composite({
  policy,
  judge,
  classification,
  retrieval,
  composite,
}: {
  policy: Policy | undefined;
  judge: JudgeScores | null;
  classification: Classification | null;
  retrieval: Retrieval | null;
  composite: number | null;
}) {
  if (!policy || composite === null || composite === undefined) return null;

  const weights = policy.composite_weights;
  const judgeScore = judge ? (judge.groundedness + judge.completeness + judge.tone) / 15 : null;
  const classifierScore = classification?.confidence ?? null;
  const retrievalScore = retrieval?.best_similarity ?? null;

  const parts = [
    { label: "judge", weight: weights.judge, score: judgeScore, note: "grades the actual draft" },
    {
      label: "classifier",
      weight: weights.classifier,
      score: classifierScore,
      note: "self-reported, weakly calibrated",
    },
    {
      label: "retrieval",
      weight: weights.retrieval,
      score: retrievalScore,
      note: "best cosine similarity, a proxy",
    },
  ];

  const threshold = policy.thresholds.auto_reply;
  const clears = composite >= threshold;

  return (
    <div className="space-y-2">
      {/* Stacked rather than tabular: this panel lives in a narrow column, and a
          four-column table collapses its headers into each other there. */}
      {parts.map((p) => {
        const contribution = p.score === null ? null : p.weight * p.score;
        return (
          <div key={p.label} className="rule-row pb-2">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs text-ink">{p.label}</span>
              <span className="tabular-nums text-xs text-ink">
                {contribution === null ? "—" : contribution.toFixed(3)}
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="prose-human text-[11px] text-ink-3">{p.note}</span>
              <span className="whitespace-nowrap tabular-nums text-[11px] text-ink-3">
                {p.weight.toFixed(2)} × {p.score === null ? "—" : p.score.toFixed(3)}
              </span>
            </div>
          </div>
        );
      })}

      <div className="flex items-baseline justify-between gap-2 pt-0.5">
        <span className="text-xs text-ink-2">composite</span>
        <span className="tabular-nums text-sm font-medium text-ink">{composite.toFixed(3)}</span>
      </div>

      <p className={`text-[11px] ${clears ? "text-teal" : "text-mustard"}`}>
        {clears
          ? `at or above the ${threshold} auto-reply threshold`
          : `${(threshold - composite).toFixed(3)} short of the ${threshold} auto-reply threshold`}
      </p>
    </div>
  );
}
