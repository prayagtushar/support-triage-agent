import { useQuery } from "@tanstack/react-query";

import { getPolicy } from "./api";

/** The thresholds every page draws against. Server-owned config, so it never goes stale mid-session. */
export function usePolicy() {
  return useQuery({ queryKey: ["policy"], queryFn: getPolicy, staleTime: Infinity }).data;
}
