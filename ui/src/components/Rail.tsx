import { useQueries, useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";

import { getStatus, listTickets } from "../lib/api";
import { relativeAge } from "../lib/format";
import { LANES } from "../lib/lanes";
import { REPO_URL } from "../lib/links";

function itemClass({ isActive }: { isActive: boolean }) {
  return [
    "flex items-center gap-2 rounded-[2px] px-2 py-1.5 text-sm transition-colors",
    isActive ? "bg-paper-2 text-ink" : "text-ink-2 hover:bg-paper-2 hover:text-ink",
  ].join(" ");
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="eyebrow px-2">{label}</p>
      {children}
    </div>
  );
}

/**
 * A dot and one word, pinned to the bottom of the rail. Whether the system is working is
 * worth saying; how long since anyone used it is not something a visitor needs, and a
 * count of recent runs reads as a usage total when it is only the health sample size.
 */
function Heartbeat() {
  const { data } = useQuery({
    queryKey: ["status"],
    queryFn: getStatus,
    refetchInterval: 30_000,
  });

  if (!data) return null;

  const detail = data.degraded
    ? data.reason
    : `Retrieval and scoring are producing output across the last ${data.runs} runs.` +
      (data.last_run_at ? ` Last ticket ${relativeAge(data.last_run_at)} ago.` : "");

  return (
    <p
      title={detail}
      className="flex items-center gap-1.5 border-t border-rule px-2 pt-3 text-[11px] text-ink-3"
    >
      <span
        aria-hidden
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${
          data.degraded ? "bg-rust-fill" : "bg-teal-fill"
        }`}
      />
      {data.degraded ? "degraded" : "running"}
    </p>
  );
}

/**
 * The console. Lanes here rather than as tabs above the table, because a lane is a place
 * you work in, and the tabs made three of them look like three views of one page.
 */
export default function Rail() {
  const counts = useQueries({
    queries: LANES.map((lane) => ({
      queryKey: ["tickets", lane.status],
      queryFn: () => listTickets(lane.status),
      refetchInterval: 10_000,
    })),
  });

  return (
    <nav aria-label="Sections" className="flex h-full flex-col gap-5">
      <Group label="queues">
        {LANES.map((lane, i) => (
          <NavLink key={lane.path} to={lane.path} end className={itemClass}>
            <span className={`h-1.5 w-1.5 rounded-full ${lane.dot}`} aria-hidden />
            {lane.label}
            <span className="ml-auto tabular-nums text-ink-3">
              {counts[i].data?.tickets.length ?? "·"}
            </span>
          </NavLink>
        ))}
        <NavLink to="/audit" className={itemClass}>
          audit
        </NavLink>
      </Group>

      <Group label="is it any good?">
        <NavLink to="/evals" className={itemClass}>
          evals
        </NavLink>
        <NavLink to="/run-it" className={itemClass}>
          run it yourself
        </NavLink>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 rounded-[2px] px-2 py-1.5 text-sm text-ink-2 transition-colors hover:bg-paper-2 hover:text-ink"
        >
          source <span aria-hidden className="text-ink-3">↗</span>
        </a>
      </Group>

      <div className="mt-auto" />
      <Heartbeat />
    </nav>
  );
}
