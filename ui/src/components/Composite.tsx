import type { JudgeScores, Policy, Retrieval, Classification } from "../lib/types";

/** The composite confidence, shown as the arithmetic that produced it. Weights come from /policy. */
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
      {/* Stacked, not tabular: this column is too narrow for four headers. */}
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
