import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { listDomains } from "./api";
import type { DomainSummary } from "./types";

/** Which desk, in the URL, so a filtered queue is still a link someone can send. */
const PARAM = "d";
const REMEMBERED = "triage.domain";

export function useDomains() {
  return useQuery({ queryKey: ["domains"], queryFn: listDomains, staleTime: 5 * 60_000 });
}

export function useDomain() {
  const [params, setParams] = useSearchParams();
  const { data } = useDomains();

  const remembered = safeRead();
  const requested = params.get(PARAM) ?? remembered ?? data?.default;
  const known = data?.domains.some((d) => d.id === requested);
  // An unknown desk in the URL falls back rather than rendering an empty console. A
  // stale bookmark from a removed domain should still land somewhere usable.
  const id = known ? requested! : (data?.default ?? "");
  const domain = data?.domains.find((d) => d.id === id);

  const setDomain = useCallback(
    (next: string) => {
      safeWrite(next);
      const merged = new URLSearchParams(params);
      merged.set(PARAM, next);
      setParams(merged);
    },
    [params, setParams],
  );

  return { id, domain, domains: data?.domains ?? [], setDomain, loading: !data };
}

/** Carries the chosen desk across an internal link. */
export function withDomain(path: string, id: string): string {
  if (!id) return path;
  const [base, query] = path.split("?");
  const merged = new URLSearchParams(query);
  merged.set(PARAM, id);
  return `${base}?${merged}`;
}

export function isReady(d: DomainSummary | undefined): boolean {
  return Boolean(d?.ready);
}

function safeRead(): string | null {
  try {
    return localStorage.getItem(REMEMBERED);
  } catch {
    // Private windows and blocked site data both throw here. A forgotten desk is fine.
    return null;
  }
}

function safeWrite(value: string): void {
  try {
    localStorage.setItem(REMEMBERED, value);
  } catch {
    /* not worth telling anyone about */
  }
}
