const NODES = ["classify", "retrieve", "draft", "score", "route"] as const;
type Node = (typeof NODES)[number];

const WHAT_IT_DID: Record<Node, string> = {
  classify: "intent, urgency and language",
  retrieve: "hybrid vector + full-text search over resolved cases",
  draft: "a grounded reply, citing what it used",
  score: "a second model, on a different vendor, grades the draft",
  route: "fixed policy over the scores above",
};

/** The pipeline as it ran, with segment widths proportional to time spent in each node. */
export function Pipeline({
  latency,
  usage,
  errors,
}: {
  latency: Record<string, number> | null;
  usage: Record<string, { model?: string; provider?: string; estimated_cost_inr: number | null }> | null;
  errors: string[] | null;
}) {
  if (!latency || Object.keys(latency).length === 0) return null;

  const ran = NODES.filter((n) => n in latency);
  const total = ran.reduce((sum, n) => sum + (latency[n] ?? 0), 0);
  const failed = new Set(
    (errors ?? []).map((e) => e.split(":")[0]?.trim()).filter((n): n is string => Boolean(n)),
  );

  return (
    <div className="space-y-3">
      {/* Proportional strip. min-w keeps a 0ms node visible; route is always 0. */}
      <div className="flex gap-[2px] overflow-hidden rounded-[2px]">
        {NODES.map((node) => {
          const ms = latency[node];
          const skipped = ms === undefined;
          const share = total > 0 && ms !== undefined ? (ms / total) * 100 : 0;
          const tone = failed.has(node)
            ? "bg-rust-fill"
            : skipped
              ? "bg-paper-3"
              : node === "route"
                ? "bg-olive-fill"
                : "bg-teal-fill";
          return (
            <div
              key={node}
              className={`animate-strip h-1.5 ${tone}`}
              style={{
                width: skipped ? "6%" : `${Math.max(share, 3)}%`,
                flexGrow: skipped ? 0 : 1,
              }}
              title={skipped ? `${node}: skipped` : `${node}: ${ms}ms`}
            />
          );
        })}
      </div>

      <ol className="space-y-0">
        {NODES.map((node) => {
          const ms = latency[node];
          const skipped = ms === undefined;
          const stats = usage?.[node];
          const broke = failed.has(node);

          return (
            <li
              key={node}
              className="rule-row flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-xs last:border-0"
            >
              <span
                className={`w-[4.5rem] font-medium ${
                  broke ? "text-rust" : skipped ? "text-ink-3" : "text-ink"
                }`}
              >
                {node}
              </span>

              <span className="tabular-nums text-ink-2">
                {skipped ? "skipped" : `${ms} ms`}
              </span>

              {stats?.model && (
                <span className="text-ink-3">
                  {stats.provider}/{stats.model}
                </span>
              )}

              {stats?.estimated_cost_inr ? (
                <span className="tabular-nums text-ink-3">
                  ₹{stats.estimated_cost_inr.toFixed(4)}
                </span>
              ) : null}

              <span className="prose-human ml-auto text-right text-ink-3">
                {skipped ? "not run, nothing to work from" : WHAT_IT_DID[node]}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="tabular-nums text-xs text-ink-3">
        {total} ms end to end
        {total > 0 && latency.route !== undefined && (
          <span> · routing decided in {latency.route} ms of ordinary code</span>
        )}
      </p>
    </div>
  );
}
