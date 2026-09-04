import type {
  AuditRow,
  DomainList,
  Policy,
  QueueRow,
  ReviewPayload,
  SystemStatus,
  TicketDetail,
  TicketProgress,
  TicketStatus,
} from "./types";
import { ownerKey } from "./ownerKey";
import { visitorId } from "./visitor";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Merge rather than overwrite: spreading init last would drop these headers.
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };

  headers["X-Visitor"] = visitorId();

  const key = ownerKey();
  if (key) headers["X-Demo-Key"] = key;

  const response = await fetch(`${BASE}${path}`, { ...init, headers });

  if (!response.ok) {
    const detail = await response.text();
    if (response.status === 403) {
      throw new Error(
        "You can review the reply to a ticket you sent. The seeded queue is left as it is, " +
          "so the next visitor finds something in it.",
      );
    }
    if (response.status === 429) {
      throw new Error(
        "The demo has reached its cap of tickets for today. It resets on a rolling " +
          "24-hour window; reading everything else still works.",
      );
    }
    throw new Error(`${response.status} ${response.statusText}: ${detail.slice(0, 200)}`);
  }
  return response.json() as Promise<T>;
}

/**
 * `domain` is required rather than optional, and that is the point: when it was
 * optional a caller could omit it and get every desk's tickets back looking entirely
 * normal. The review screen did exactly that, so j/k walked out of a refund and into a
 * laptop that would not charge. A queue that quietly mixes desks is worse than an empty
 * one, because every row looks legitimate. Pass "" deliberately to span every desk.
 */
export function listTickets(status: TicketStatus | undefined, domain: string, lang = "") {
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (domain) query.set("domain", domain);
  // Filtered server side, not in the component, so the rail's lane counts keep
  // agreeing with the rows underneath them.
  if (lang) query.set("lang", lang);
  const suffix = query.toString() ? `?${query}` : "";
  return request<{ tickets: QueueRow[] }>(`/tickets${suffix}`);
}

export function getTicket(id: string) {
  return request<TicketDetail>(`/tickets/${id}`);
}

export function submitReview(id: string, payload: ReviewPayload) {
  return request<{ review_id: string; status: string }>(`/tickets/${id}/review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listAudit() {
  return request<{ actions: AuditRow[] }>("/audit");
}

export function createTicket(subject: string, body: string, domain?: string) {
  return request<{ ticket_id: string }>("/tickets", {
    method: "POST",
    body: JSON.stringify({ subject, body, domain_id: domain }),
  });
}

export function listDomains() {
  return request<DomainList>("/domains");
}

export function getPolicy() {
  return request<Policy>("/policy");
}

export function getStatus() {
  return request<SystemStatus>("/status");
}

export function getProgress(id: string) {
  return request<TicketProgress>(`/tickets/${id}/progress`);
}
