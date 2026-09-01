import { useState } from "react";

/** A failed fetch, said in words. The raw error is kept, behind a toggle, for whoever wants it. */
export function ErrorNote({ error, what }: { error: unknown; what: string }) {
  const [open, setOpen] = useState(false);
  const detail = error instanceof Error ? error.message : String(error);

  return (
    <div role="alert" className="rounded-[2px] border border-rust/40 bg-rust-bg p-3">
      <p className="prose-human text-sm text-rust">Could not load {what}.</p>
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="mt-1 text-[11px] text-rust/80 underline-offset-2 hover:underline"
      >
        {open ? "hide detail" : "show detail"}
      </button>
      {open && (
        <pre className="mt-2 overflow-x-auto text-[11px] leading-relaxed text-rust/90">
          {detail}
        </pre>
      )}
    </div>
  );
}

/** Rows at the height they will settle at, so the page does not jump when data lands. */
export function Skeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div aria-hidden className="space-y-px">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="rule-row flex items-center gap-4 py-3">
          <div className="h-2.5 flex-1 rounded-[1px] bg-paper-3 opacity-60" />
          <div className="h-2.5 w-16 rounded-[1px] bg-paper-3 opacity-40" />
          <div className="h-2.5 w-20 rounded-[1px] bg-paper-3 opacity-40" />
        </div>
      ))}
    </div>
  );
}
