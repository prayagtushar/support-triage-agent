import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Tone = "ok" | "bad";
type Toast = { id: number; text: string; tone: Tone };

const ToastContext = createContext<(text: string, tone?: Tone) => void>(() => {});

/** Say that something happened. Acting on a ticket changes a row somewhere off screen,
 *  and an action with no acknowledgement reads as a click that did not land. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((text: string, tone: Tone = "ok") => {
    setToasts((t) => [...t, { id: Date.now() + Math.random(), text, tone }]);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 left-1/2 z-50 flex w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 flex-col gap-2"
      >
        {toasts.map((t) => (
          <Item key={t.id} toast={t} onDone={() => setToasts((x) => x.filter((i) => i.id !== t.id))} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function Item({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  useEffect(() => {
    // Long enough to read, short enough not to sit over the next row you are working on.
    const timer = setTimeout(onDone, 3200);
    return () => clearTimeout(timer);
  }, [onDone]);

  return (
    <div
      role="status"
      className={`pointer-events-auto rounded-[2px] border px-3 py-2 text-xs shadow-[var(--shadow)] ${
        toast.tone === "bad"
          ? "border-rust/40 bg-rust-bg text-rust"
          : "border-rule-2 bg-paper text-ink"
      }`}
    >
      {toast.text}
    </div>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

/** Stable labels for the three review actions, so the wording cannot drift between them. */
export function reviewToast(action: string, next?: string): string {
  const said = { approve: "Approved and sent", edit: "Edit sent", reject: "Rejected" }[action];
  return next ? `${said ?? "Recorded"}. Next ticket.` : `${said ?? "Recorded"}.`;
}
