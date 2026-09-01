/**
 * Two plots, drawn as SVG against the same data the tables read. No chart library:
 * both are a handful of points on fixed axes, and a dependency would be larger than
 * the code it replaced.
 */

type Point = { x: number; y: number };

const W = 320;
const H = 180;
const PAD = { top: 10, right: 10, bottom: 22, left: 30 };

const plotW = W - PAD.left - PAD.right;
const plotH = H - PAD.top - PAD.bottom;

function scale(domain: [number, number]) {
  const [lo, hi] = domain;
  return {
    x: (v: number) => PAD.left + ((v - lo) / (hi - lo)) * plotW,
    y: (v: number) => PAD.top + (1 - v) * plotH,
  };
}

function path(points: Point[], s: ReturnType<typeof scale>) {
  return points.map((p, i) => `${i ? "L" : "M"}${s.x(p.x)} ${s.y(p.y)}`).join(" ");
}

function Frame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={label}
      className="w-full max-w-md overflow-visible"
    >
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={PAD.top + (1 - t) * plotH}
            y2={PAD.top + (1 - t) * plotH}
            className="stroke-rule"
            strokeWidth={1}
          />
          {/* Only the halves are labelled: 0.25 rounds to 0.3 at one decimal and reads wrong. */}
          {(t === 0 || t === 0.5 || t === 1) && (
            <text
              x={PAD.left - 6}
              y={PAD.top + (1 - t) * plotH + 3}
              textAnchor="end"
              className="fill-ink-3 text-[8px]"
            >
              {t.toFixed(1)}
            </text>
          )}
        </g>
      ))}
      {children}
    </svg>
  );
}

export type SweepPoint = {
  threshold: number;
  auto_reply_precision: number;
  review_recall: number;
  auto_replied: number;
};

/**
 * The trade-off the threshold buys, as a curve. The operating point is marked because
 * a single number in a table cannot show what was given up to reach it.
 */
export function SweepChart({
  sweep,
  threshold,
  target,
}: {
  sweep: SweepPoint[];
  threshold: number;
  target?: number;
}) {
  const xs = sweep.map((s) => s.threshold);
  const s = scale([Math.min(...xs), Math.max(...xs)]);

  const precision = sweep.map((p) => ({ x: p.threshold, y: p.auto_reply_precision }));
  const recall = sweep.map((p) => ({ x: p.threshold, y: p.review_recall }));

  return (
    <div className="space-y-2">
      <Frame label="Auto-reply precision and review recall across the threshold sweep">
        {target !== undefined && (
          <>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={s.y(target)}
              y2={s.y(target)}
              className="stroke-rust"
              strokeWidth={1}
              strokeDasharray="3 3"
            />
            <text x={W - PAD.right} y={s.y(target) - 4} textAnchor="end" className="fill-rust text-[8px]">
              target {target}
            </text>
          </>
        )}

        <line
          x1={s.x(threshold)}
          x2={s.x(threshold)}
          y1={PAD.top}
          y2={PAD.top + plotH}
          className="stroke-ink"
          strokeWidth={1.5}
          opacity={0.55}
        />

        <path d={path(precision, s)} fill="none" className="stroke-teal-fill" strokeWidth={1.75} />
        <path d={path(recall, s)} fill="none" className="stroke-mustard-fill" strokeWidth={1.75} />

        {sweep.map((p) => (
          <circle
            key={p.threshold}
            cx={s.x(p.threshold)}
            cy={s.y(p.auto_reply_precision)}
            r={p.threshold === threshold ? 3 : 1.75}
            className="fill-teal-fill"
          />
        ))}

        {xs.map((t) => (
          <text key={t} x={s.x(t)} y={H - 6} textAnchor="middle" className="fill-ink-3 text-[8px]">
            {t.toFixed(2)}
          </text>
        ))}
      </Frame>

      <p className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-3">
        <span className="flex items-center gap-1.5">
          <span className="h-[2px] w-3 bg-teal-fill" /> auto-reply precision
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-[2px] w-3 bg-mustard-fill" /> review recall
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-[1.5px] bg-ink/55" /> threshold in force
        </span>
      </p>
    </div>
  );
}

export type ReliabilityBucket = {
  lower: number;
  upper: number;
  n: number;
  mean_confidence: number;
  observed_correct: number;
};

/**
 * Stated against observed. Everything under the diagonal is a bucket claiming more than
 * it delivered, which on this corpus is all of them.
 */
export function ReliabilityChart({ buckets }: { buckets: ReliabilityBucket[] }) {
  const s = scale([0.5, 1]);
  const maxN = Math.max(...buckets.map((b) => b.n), 1);

  return (
    <div className="space-y-2">
      <Frame label="Reliability diagram: stated confidence against observed accuracy">
        <line
          x1={s.x(0.5)}
          y1={s.y(0.5)}
          x2={s.x(1)}
          y2={s.y(1)}
          className="stroke-ink-3"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        <text x={s.x(0.98)} y={s.y(0.99)} textAnchor="end" className="fill-ink-3 text-[8px]">
          perfect
        </text>

        {buckets.map((b) => (
          <g key={b.lower}>
            <line
              x1={s.x(b.mean_confidence)}
              x2={s.x(b.mean_confidence)}
              y1={s.y(b.mean_confidence)}
              y2={s.y(b.observed_correct)}
              className="stroke-rust"
              strokeWidth={1}
              opacity={0.5}
            />
            <circle
              cx={s.x(b.mean_confidence)}
              cy={s.y(b.observed_correct)}
              r={3 + (b.n / maxN) * 4}
              className="fill-rust-fill"
              opacity={0.85}
            />
          </g>
        ))}

        {[0.5, 0.6, 0.7, 0.8, 0.9, 1].map((t) => (
          <text key={t} x={s.x(t)} y={H - 6} textAnchor="middle" className="fill-ink-3 text-[8px]">
            {t.toFixed(1)}
          </text>
        ))}
      </Frame>

      <p className="text-[11px] text-ink-3">
        Stated confidence across, observed accuracy up. Dot size is how many tickets fell in
        the bucket; the drop line is the gap.
      </p>
    </div>
  );
}
