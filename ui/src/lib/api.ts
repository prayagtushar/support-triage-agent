import type { AuditRow, QueueRow, ReviewPayload, TicketDetail, TicketStatus } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
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
