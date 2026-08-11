import type { Policy } from "../lib/types";

/** The confidence meter: distance from the threshold is what actually decided the ticket. */
export function ConfidenceMeter({
  value,
  policy,
  width = "w-20",
  showValue = true,
}: {
  value: number | null;
  policy: Policy | undefined;
  width?: string;
  showValue?: boolean;
}) {
  if (value === null || value === undefined) {
    return <span className="text-ink-3 tabular-nums">—</span>;
  }

  const auto = policy?.thresholds.auto_reply ?? 0.9;
  const review = policy?.thresholds.review ?? 0.55;

  const band = value >= auto ? "auto" : value >= review ? "review" : "escalate";
  const fill =
    band === "auto" ? "bg-teal-fill" : band === "review" ? "bg-mustard-fill" : "bg-rust-fill";

  const pct = Math.max(0, Math.min(1, value)) * 100;

  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`relative ${width} h-[7px] overflow-hidden rounded-[1px] bg-paper-3`}
        role="img"
        aria-label={`confidence ${value.toFixed(2)}, auto-reply threshold ${auto}`}
      >
        <span
          className={`absolute inset-y-0 left-0 ${fill}`}
          style={{ width: `${pct}%` }}
        />
        {/* The line the score is measured against, above the fill so it stays visible. */}
        <span
          className="absolute inset-y-0 w-[1.5px] bg-ink/55"
          style={{ left: `${auto * 100}%` }}
        />
      </span>
      {showValue && (
        <span className="tabular-nums text-xs text-ink-2">{value.toFixed(2)}</span>
      )}
    </span>
  );
}

/** A 0-5 judge sub-score as five ticks: counting marks beats comparing "3/5" to "5/5". */
export function ScoreTicks({ value, tone }: { value: number; tone: "teal" | "mustard" | "rust" }) {
  const color =
    tone === "teal" ? "bg-teal-fill" : tone === "mustard" ? "bg-mustard-fill" : "bg-rust-fill";
  return (
    <span className="inline-flex items-center gap-[3px]" aria-label={`${value} of 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          className={`h-3.5 w-[3px] rounded-[1px] ${n <= value ? color : "bg-paper-3"}`}
        />
      ))}
    </span>
  );
}

export function scoreTone(value: number): "teal" | "mustard" | "rust" {
  if (value >= 4) return "teal";
  if (value >= 3) return "mustard";
  return "rust";
}
