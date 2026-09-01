const STORAGE = "triage-visitor";

let cached: string | null = null;

/**
 * A random id this browser keeps, sent with every write. It is not a login and not a rate
 * limit: it is how the server knows which tickets you sent, so you can review the reply to
 * your own without being able to clear the seeded queue for the next person.
 */
export function visitorId(): string {
  if (cached) return cached;

  try {
    cached = window.localStorage.getItem(STORAGE) ?? crypto.randomUUID();
    window.localStorage.setItem(STORAGE, cached);
  } catch {
    // A private window gets an id for this page load and loses it on reload. That costs
    // the ability to review your own ticket after a refresh, and nothing else.
    cached = crypto.randomUUID();
  }

  return cached;
}
