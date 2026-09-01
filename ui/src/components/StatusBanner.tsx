import { useQuery } from "@tanstack/react-query";

import { getStatus } from "../lib/api";

/**
 * Says out loud when the system is serving but not working. Silent otherwise — the rail
 * carries the heartbeat, so this stays an alert rather than becoming furniture.
 */
export default function StatusBanner() {
  const { data } = useQuery({
    queryKey: ["status"],
    queryFn: getStatus,
    refetchInterval: 30_000,
  });

  if (!data?.degraded) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-6 rounded-[2px] border border-rust/40 bg-rust-bg px-3 py-2 text-xs text-rust"
    >
      <span className="font-medium">Retrieval is degraded.</span>{" "}
      <span className="prose-human">
        {data.reason}. Drafts are being written without grounding, so every ticket is routed
        to a human by policy. The routing is correct; the evidence is missing.
      </span>
    </div>
  );
}
