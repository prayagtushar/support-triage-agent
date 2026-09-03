import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { listTickets } from "../lib/api";
import { useDomain, withDomain } from "../lib/domain";
import { LANES } from "../lib/lanes";

type Command = { id: string; label: string; hint?: string; run: () => void };

/**
 * Cmd-K. Everything reachable without leaving the keyboard.
 *
 * The review screen is already keyboard-driven (j, k, a, e, r), so the gap was getting
 * TO a screen. Switching desk belongs here more than anywhere: it is the one action that
 * changes what every other screen means, and burying it in a menu makes it feel rare.
 */
export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const { id: domainId, domains, setDomain } = useDomain();

  // Only fetched while the palette is open: it exists to jump to a ticket, not to poll.
  const { data } = useQuery({
    queryKey: ["palette-tickets", domainId],
    queryFn: () => listTickets(undefined, domainId),
    enabled: open && Boolean(domainId),
    staleTime: 30_000,
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
        setQuery("");
        setCursor(0);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const go = (path: string) => () => {
      navigate(withDomain(path, domainId));
      setOpen(false);
    };

    const list: Command[] = [
      ...LANES.map((l) => ({ id: `lane-${l.path}`, label: l.label, hint: "queue", run: go(l.path) })),
      { id: "desks", label: "all desks", hint: "compare", run: go("/desks") },
      { id: "evals", label: "evals", hint: "measurement", run: go("/evals") },
      { id: "audit", label: "audit", hint: "history", run: go("/audit") },
      { id: "submit", label: "send a ticket", hint: "demo", run: go("/submit") },
      { id: "voice", label: "say it instead", hint: "voice", run: go("/voice") },
      ...domains.map((d) => ({
        id: `domain-${d.id}`,
        label: `switch to ${d.name}`,
        hint: d.provenance === "synthetic" ? "generated desk" : "desk",
        run: () => {
          setDomain(d.id);
          setOpen(false);
        },
      })),
      ...(data?.tickets ?? []).slice(0, 40).map((t) => ({
        id: `ticket-${t.id}`,
        label: t.subject,
        hint: t.intent ?? "ticket",
        run: go(`/tickets/${t.id}`),
      })),
    ];

    const q = query.trim().toLowerCase();
    return q ? list.filter((c) => `${c.label} ${c.hint ?? ""}`.toLowerCase().includes(q)) : list;
  }, [query, navigate, domainId, domains, setDomain, data]);

  if (!open) return null;

  const clamped = Math.min(cursor, Math.max(commands.length - 1, 0));

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-ink/20 pt-[12vh]"
      onMouseDown={() => setOpen(false)}
    >
      <div
        role="dialog"
        aria-label="Command palette"
        onMouseDown={(e) => e.stopPropagation()}
        className="w-[min(34rem,calc(100vw-2rem))] overflow-hidden rounded-[2px] border border-rule-2 bg-paper shadow-[var(--shadow)]"
      >
        <input
          ref={input}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setCursor(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setCursor((c) => Math.min(c + 1, commands.length - 1));
            }
            if (e.key === "ArrowUp") {
              e.preventDefault();
              setCursor((c) => Math.max(c - 1, 0));
            }
            if (e.key === "Enter") {
              e.preventDefault();
              commands[clamped]?.run();
            }
          }}
          placeholder="Jump to a queue, a desk, or a ticket"
          className="w-full border-b border-rule bg-paper-2 px-3 py-2.5 text-sm outline-none"
        />
        <ul className="max-h-80 overflow-y-auto py-1">
          {commands.length === 0 && (
            <li className="px-3 py-3 text-xs text-ink-3">Nothing matches that.</li>
          )}
          {commands.map((c, i) => (
            <li key={c.id}>
              <button
                onMouseEnter={() => setCursor(i)}
                onClick={c.run}
                className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-xs ${
                  i === clamped ? "bg-paper-2 text-ink" : "text-ink-2"
                }`}
              >
                <span className="truncate">{c.label}</span>
                {c.hint && <span className="shrink-0 text-[10px] text-ink-3">{c.hint}</span>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
