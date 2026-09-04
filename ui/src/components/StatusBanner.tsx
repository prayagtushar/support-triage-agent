import { useQuery } from "@tanstack/react-query";

import { getStatus } from "../lib/api";

/**
 * Says out loud when the system is serving but not working. Silent otherwise, because the rail
 * carries the heartbeat, so this stays an alert rather than becoming furniture.
 */
export default function StatusBanner() {
  const { data } = useQuery({
    queryKey: ["status"],
    queryFn: getStatus,
    refetchInterval: 30_000,
  });

  if (!data?.degraded) return null;

  // The two ways this system serves without working need different words. Saying
  // "retrieval is degraded" while the drafter is the broken part sends whoever reads
  // this to the wrong component, which is worse than saying nothing.
  const drafting = data.degraded_kind === "drafting";
  const headline = drafting ? "Drafting is degraded." : "Retrieval is degraded.";
  const detail = drafting
    ? "The pipeline is finding evidence and then returning no reply, so every ticket is " +
      "routed to a human by policy. The routing is correct; the draft is missing."
    : "Drafts are being written without grounding, so every ticket is routed to a human " +
      "by policy. The routing is correct; the evidence is missing.";

  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-6 rounded-[2px] border border-rust/40 bg-rust-bg px-3 py-2 text-xs text-rust"
    >
      <span className="font-medium">{headline}</span>{" "}
      <span className="prose-human">
        {data.reason}. {detail}
      </span>
    </div>
  );
}
