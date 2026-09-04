import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useDomain, withDomain } from "../lib/domain";

/**
 * Which desk you are looking at, always on screen.
 *
 * It is a button rather than a select because it carries more than a name: how much work
 * is waiting on each desk, so switching is a decision rather than a guess.
 */
export default function DomainSwitcher() {
  const { id, domain, domains, setDomain } = useDomain();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  if (domains.length < 2 && !domain) return null;

  return (
    <div className="relative" ref={box}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex max-w-[9rem] items-center gap-1.5 whitespace-nowrap rounded-[2px] border border-rule bg-paper px-2 py-1.5 text-xs transition-colors hover:border-rule-2 sm:max-w-none sm:gap-2 sm:px-2.5"
      >
        <span className="truncate font-medium text-ink">{domain?.name ?? "choose a desk"}</span>
        <span aria-hidden className="text-ink-3">
          ▾
        </span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-[min(18rem,calc(100vw-2rem))] rounded-[2px] border border-rule bg-paper p-1 shadow-[var(--shadow)]"
        >
          {domains.map((d) => (
            <button
              key={d.id}
              role="menuitem"
              onClick={() => {
                setDomain(d.id);
                setOpen(false);
              }}
              className={`flex w-full flex-col gap-0.5 rounded-[2px] px-2 py-2 text-left transition-colors hover:bg-paper-2 ${
                d.id === id ? "bg-paper-2" : ""
              }`}
            >
              <span className="flex items-center gap-2">
                <span className="text-xs font-medium text-ink">{d.name}</span>
                {!d.ready && (
                  <span className="rounded-[1px] bg-rust-bg px-1 py-px text-[10px] text-rust">
                    no cases
                  </span>
                )}
              </span>
              <span className="text-[11px] text-ink-3">
                {d.tickets} tickets · {d.in_review} awaiting review
              </span>
            </button>
          ))}
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              navigate(withDomain("/desks", id));
            }}
            className="mt-1 w-full border-t border-rule px-2 py-2 text-left text-[11px] text-ink-2 hover:bg-paper-2"
          >
            compare every desk →
          </button>
        </div>
      )}
    </div>
  );
}
