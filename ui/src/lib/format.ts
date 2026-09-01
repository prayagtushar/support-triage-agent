export function relativeAge(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/** Hours a ticket of each priority is expected to be answered within. */
const RESPONSE_WINDOW_HOURS = { P1: 4, P2: 24, P3: 72, P4: 168 } as const;

/** Age is a risk signal in a queue, not a neutral fact, so it is coloured like one. */
export function ageTone(iso: string, urgency: keyof typeof RESPONSE_WINDOW_HOURS | null): string {
  if (!urgency) return "text-ink-3";
  const hours = (Date.now() - new Date(iso).getTime()) / 3_600_000;
  const window = RESPONSE_WINDOW_HOURS[urgency];
  if (hours > window * 2) return "text-rust";
  if (hours > window) return "text-mustard";
  return "text-ink-3";
}

export function timestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
