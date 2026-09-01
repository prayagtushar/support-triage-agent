import { useEffect } from "react";

/**
 * Single-key shortcuts, ignored while the caret is in a field. No dependency array:
 * re-binding each render is cheaper than reasoning about a stale closure over `data`.
 */
export function useHotkeys(map: Record<string, (() => void) | undefined>) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }

      const handler = map[event.key];
      if (handler) {
        event.preventDefault();
        handler();
      }
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
}
