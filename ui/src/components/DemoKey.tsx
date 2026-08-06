import { useState } from "react";

import { getDemoKey, setDemoKey } from "../lib/api";

/**
 * Key entry for the write endpoints.
 *
 * Browsing the queues, drafts, citations and audit trail needs nothing. Only
 * recording a review does, because that mutates the audit trail. The key is
 * kept in localStorage rather than compiled into the bundle: a key baked into
 * a static build is public the moment someone opens devtools.
 */
export default function DemoKey() {
  const [value, setValue] = useState(getDemoKey());
  const [saved, setSaved] = useState(false);
  const [open, setOpen] = useState(false);

  const active = getDemoKey() !== "";

  function save() {
    setDemoKey(value.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-300"
        title={
          active
            ? "A demo key is set. Reviews will be accepted."
            : "Read-only. Set a demo key to record reviews."
        }
      >
        {active ? "review key set" : "read-only"}
      </button>
    );
  }

  return (
    <span className="flex items-center gap-2">
      <input
        type="password"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && save()}
        placeholder="demo key"
        aria-label="Demo key"
        className="w-40 rounded border border-neutral-300 bg-transparent px-2 py-1 text-xs dark:border-neutral-700"
      />
      <button onClick={save} className="text-xs text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100">
        {saved ? "saved" : "save"}
      </button>
      <button
        onClick={() => setOpen(false)}
        className="text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-300"
        aria-label="Close key entry"
      >
        ×
      </button>
    </span>
  );
}
