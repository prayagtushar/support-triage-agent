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
        className={`rounded-[2px] border px-2 py-1 text-[11px] transition-colors ${
          active
            ? "border-teal/40 bg-teal-bg text-teal"
            : "border-rule text-ink-3 hover:border-rule-2 hover:text-ink"
        }`}
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
        className="w-36 rounded-[2px] border border-rule bg-paper-2 px-2 py-1 text-[11px]"
      />
      <button onClick={save} className="text-[11px] text-ink-2 hover:text-ink">
        {saved ? "saved" : "save"}
      </button>
      <button
        onClick={() => setOpen(false)}
        className="text-[11px] text-ink-3 hover:text-ink"
        aria-label="Close key entry"
      >
        ×
      </button>
    </span>
  );
}
