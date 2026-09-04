import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { listDomains } from "./api";
import type { DomainSummary } from "./types";

/** Which desk, in the URL, so a filtered queue is still a link someone can send. */
const PARAM = "d";
const REMEMBERED = "triage.domain";

/** Which languages a reader wants to see. "" is all of them, and is the default. */
const LANG_PARAM = "lang";
const LANG_REMEMBERED = "triage.language";
const LANGUAGES = ["", "en", "hi"] as const;

export type Language = (typeof LANGUAGES)[number];

export function useDomains() {
  return useQuery({ queryKey: ["domains"], queryFn: listDomains, staleTime: 5 * 60_000 });
}

export function useDomain() {
  const [params, setParams] = useSearchParams();
  const { data } = useDomains();

  const remembered = safeRead(REMEMBERED);
  const requested = params.get(PARAM) ?? remembered ?? data?.default;
  const known = data?.domains.some((d) => d.id === requested);
  // An unknown desk in the URL falls back rather than rendering an empty console. A
  // stale bookmark from a removed domain should still land somewhere usable.
  const id = known ? requested! : (data?.default ?? "");
  const domain = data?.domains.find((d) => d.id === id);

  const setDomain = useCallback(
    (next: string) => {
      safeWrite(REMEMBERED, next);
      const merged = new URLSearchParams(params);
      merged.set(PARAM, next);
      setParams(merged);
    },
    [params, setParams],
  );

  return { id, domain, domains: data?.domains ?? [], setDomain, loading: !data };
}

/**
 * The corpus is English and Hinglish. Someone who cannot read one of them cannot judge
 * those rows, so this is a reading aid rather than a claim about the desk, and it lives
 * in the URL so a filtered queue is still a link someone can send.
 */
export function useLanguage() {
  const [params, setParams] = useSearchParams();

  const requested = params.get(LANG_PARAM) ?? safeRead(LANG_REMEMBERED) ?? "";
  // An unknown value shows everything rather than emptying the queue, which matches
  // what the API does with the same query string.
  const lang = (LANGUAGES as readonly string[]).includes(requested)
    ? (requested as Language)
    : "";

  const setLanguage = useCallback(
    (next: Language) => {
      safeWrite(LANG_REMEMBERED, next);
      const merged = new URLSearchParams(params);
      if (next) merged.set(LANG_PARAM, next);
      else merged.delete(LANG_PARAM);
      setParams(merged);
    },
    [params, setParams],
  );

  return { lang, setLanguage };
}

/** Carries the chosen desk across an internal link. */
export function withDomain(path: string, id: string): string {
  const [base, query] = path.split("?");
  const merged = new URLSearchParams(query);
  if (id) merged.set(PARAM, id);
  // The language filter rides along rather than being threaded through eleven call
  // sites. A link that dropped it would silently unfilter the queue mid-session.
  const lang = new URLSearchParams(window.location.search).get(LANG_PARAM);
  if (lang && !merged.has(LANG_PARAM)) merged.set(LANG_PARAM, lang);
  const query_ = merged.toString();
  return query_ ? `${base}?${query_}` : base;
}

export function isReady(d: DomainSummary | undefined): boolean {
  return Boolean(d?.ready);
}

function safeRead(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    // Private windows and blocked site data both throw here. A forgotten desk is fine.
    return null;
  }
}

function safeWrite(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* not worth telling anyone about */
  }
}
