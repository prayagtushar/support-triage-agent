const STORAGE = "triage-owner-key";

/**
 * The owner's key, claimed once from `?key=...` and then kept. There is no field for it
 * anywhere in the dashboard: a visitor has nothing to type it into, and the only person
 * who needs it already has the link. Visiting with the parameter strips it from the URL
 * so it does not end up in a screenshot or a shared address.
 */
export function ownerKey(): string {
  try {
    const url = new URL(window.location.href);
    const claimed = url.searchParams.get("key");

    if (claimed) {
      window.localStorage.setItem(STORAGE, claimed);
      url.searchParams.delete("key");
      window.history.replaceState({}, "", url);
      return claimed;
    }

    return window.localStorage.getItem(STORAGE) ?? "";
  } catch {
    return "";
  }
}
