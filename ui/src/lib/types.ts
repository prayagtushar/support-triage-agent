// Typed by hand against the FastAPI response models, which keeps the contract visible.

export type Route = "auto_reply" | "human_review" | "escalate";
export type Urgency = "P1" | "P2" | "P3" | "P4";
export type Language = "en" | "hi-en" | "hi" | "unknown";
export type TicketStatus =
  | "received"
  | "triaged"
  | "auto_replied"
  | "in_review"
  | "resolved"
  | "escalated";

export interface QueueRow {
  id: string;
  subject: string;
  status: TicketStatus;
  channel: string;
  created_at: string;
  run_id: string | null;
  route: Route | null;
  composite_confidence: number | null;
  intent: string | null;
  urgency: Urgency | null;
  language: Language | null;
}

export interface Classification {
  intent: string;
  urgency: Urgency;
  language: Language;
  sentiment: string;
  confidence: number;
  rationale: string;
}

export interface RetrievedCase {
  case_id: string;
  intent: string;
  language: string;
  customer_text: string;
  resolution_text: string;
  score: number;
  similarity: number;
}

export interface Retrieval {
  cases: RetrievedCase[];
  weak: boolean;
  best_similarity: number;
}

export interface JudgeScores {
  groundedness: number;
  completeness: number;
  tone: number;
  notes: string;
}

export interface TicketDetail {
  id: string;
  subject: string;
  body: string;
  channel: string;
  status: TicketStatus;
  created_at: string;
  run_id: string | null;
  classification: Classification | null;
  retrieval: Retrieval | null;
  draft: string | null;
  draft_citations: number[] | null;
  judge_scores: JudgeScores | null;
  composite_confidence: number | null;
  route: Route | null;
  route_reason: string | null;
  errors: string[] | null;
  latency_ms: Record<string, number> | null;
  token_usage: Record<
    string,
    {
      model?: string;
      provider?: string;
      attempts?: number;
      prompt_tokens?: number;
      completion_tokens?: number;
      estimated_cost_inr: number | null;
    }
  > | null;
  langfuse_trace_id: string | null;
  reviewable: boolean;
}

export type RejectReason =
  | "hallucinated"
  | "wrong_intent"
  | "wrong_tone"
  | "missing_info"
  | "not_answerable"
  | "other";

export interface AuditRow {
  id: string;
  action: "approve" | "edit" | "reject";
  reviewer: string;
  note: string | null;
  reason: RejectReason | null;
  final_text: string | null;
  original_text: string | null;
  created_at: string;
  run_id: string;
  route: Route | null;
  composite_confidence: number | null;
  ticket_id: string;
  subject: string;
}

export interface ReviewPayload {
  action: "approve" | "edit" | "reject";
  final_text?: string;
  note?: string;
  reason?: RejectReason;
}

export interface Policy {
  thresholds: {
    auto_reply: number;
    review: number;
    weak_retrieval_floor: number;
  };
  composite_weights: {
    judge: number;
    classifier: number;
    retrieval: number;
  };
  models: Record<string, string>;
  max_tickets_per_day: number;
}

export interface SystemStatus {
  runs: number;
  degraded: boolean;
  reason: string;
  empty_retrieval_rate?: number;
  error_rate?: number;
  routes?: Record<string, number>;
  tickets_last_24h?: number;
  last_run_at?: string | null;
  reject_reasons?: Record<string, number>;
}

export interface TicketProgress {
  status: TicketStatus;
  progress_available: boolean;
  completed: string[];
  skipped: string[];
  classification?: Classification | null;
  retrieved_count?: number;
  errors?: string[];
}
