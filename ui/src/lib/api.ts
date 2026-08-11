import type {
  AuditRow,
  Policy,
  QueueRow,
  ReviewPayload,
  SystemStatus,
  TicketDetail,
  TicketProgress,
  TicketStatus,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const DEMO_KEY_STORAGE = "triage-demo-key";

/** The key for the two endpoints that cost money. In localStorage, not the bundle. */
export function getDemoKey(): string {
  return localStorage.getItem(DEMO_KEY_STORAGE) ?? "";
}

export function setDemoKey(key: string): void {
  if (key) localStorage.setItem(DEMO_KEY_STORAGE, key);
  else localStorage.removeItem(DEMO_KEY_STORAGE);
}

export class WriteKeyError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Merge rather than overwrite: spreading init last would drop these headers.
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };

  const key = getDemoKey();
  if (key) headers["X-Demo-Key"] = key;

  const response = await fetch(`${BASE}${path}`, { ...init, headers });

  if (!response.ok) {
    const detail = await response.text();
    if (response.status === 401) {
      throw new WriteKeyError(
        "This action needs a demo key. Reading the queues is open to everyone; " +
          "submitting tickets and recording reviews is not.",
      );
    }
    if (response.status === 429) {
      throw new Error(
        "The daily demo limit has been reached. It resets on a rolling 24-hour window.",
      );
    }
    throw new Error(`${response.status} ${response.statusText}: ${detail.slice(0, 200)}`);
  }
  return response.json() as Promise<T>;
}

export function listTickets(status?: TicketStatus) {
  const query = status ? `?status=${status}` : "";
  return request<{ tickets: QueueRow[] }>(`/tickets${query}`);
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

export function createTicket(subject: string, body: string) {
  return request<{ ticket_id: string }>("/tickets", {
    method: "POST",
    body: JSON.stringify({ subject, body }),
  });
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
