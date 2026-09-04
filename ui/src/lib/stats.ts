/**
 * Wilson score interval. The normal approximation is wrong at the sample sizes this
 * project reports. Auto-reply precision rests on about ten tickets, and a
 * proportion quoted to three decimals without one invites the reader to believe it.
 */
export function wilson(successes: number, n: number, z = 1.96): [number, number] {
  if (n === 0) return [0, 1];

  const p = successes / n;
  const denominator = 1 + (z * z) / n;
  const centre = p + (z * z) / (2 * n);
  const spread = z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n));

  return [
    Math.max(0, (centre - spread) / denominator),
    Math.min(1, (centre + spread) / denominator),
  ];
}

/** "5/10" as the eval reports write it. Returns null when a detail string is absent. */
function parseDetail(detail: string | undefined): { hits: number; n: number } | null {
  const match = /^(\d+)\/(\d+)$/.exec(detail ?? "");
  return match ? { hits: Number(match[1]), n: Number(match[2]) } : null;
}

export function formatInterval(detail: string | undefined): string | null {
  const parsed = parseDetail(detail);
  if (!parsed || parsed.n === 0) return null;
  const [lo, hi] = wilson(parsed.hits, parsed.n);
  return `95% CI ${lo.toFixed(2)}–${hi.toFixed(2)} · n=${parsed.n}`;
}
