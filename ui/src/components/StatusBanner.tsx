import { useQuery } from "@tanstack/react-query";

import { getStatus } from "../lib/api";

/**
 * Says out loud when the system is serving but not working.
 *
 * This exists because of a real outage: the embedding key ran out of credit, so
 * every retrieval returned nothing, every ticket went to a human by hard rule,
 * and nothing else changed. No request failed, no ticket stalled, the health
 * endpoint stayed green and the queues still rendered. The only symptom was two
 * empty lanes, which reads as a quiet day rather than a broken dependency.
 *
 * Silent when healthy. A banner that is always present is furniture, and gets
 * read as decoration rather than as a warning.
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
      className="mb-6 rounded-[2px] border border-rust/40 bg-rust-bg px-3 py-2 text-xs text-rust"
    >
      <span className="font-medium">Retrieval is degraded.</span>{" "}
      <span className="prose-human">
        {data.reason}. Drafts are being written without grounding, so every ticket is
        routed to a human by policy. The routing is correct; the evidence is missing.
      </span>
    </div>
  );
}
