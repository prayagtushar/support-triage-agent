import "@testing-library/jest-dom/vitest";

/**
 * Bun installs its own `localStorage` global that shadows the jsdom one, and in this
 * environment it carries none of the Storage methods — not even getItem. Without this the
 * dashboard's storage code silently takes its catch branch under test and every
 * assertion about remembering something passes for the wrong reason.
 */
function memoryStorage(): Storage {
  let entries = new Map<string, string>();

  return {
    get length() {
      return entries.size;
    },
    key: (i: number) => [...entries.keys()][i] ?? null,
    getItem: (k: string) => entries.get(k) ?? null,
    setItem: (k: string, v: string) => void entries.set(k, String(v)),
    removeItem: (k: string) => void entries.delete(k),
    clear: () => {
      entries = new Map();
    },
  };
}

Object.defineProperty(window, "localStorage", {
  value: memoryStorage(),
  configurable: true,
  writable: true,
});
