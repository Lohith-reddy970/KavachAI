// KAVACH AI — shared domain types.
// These mirror the FastAPI backend contract so the UI can later switch from the
// baked mock-data layer to live endpoints without changing components.

export type Classification = "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED";
export type ProcessState = "pending" | "running" | "done" | "error";

export interface KDocument {
  id: string;
  name: string;
  type: string; // PDF, PNG, ...
  sizeBytes: number;
  pages: number;
  classification: Classification;
  ocr: ProcessState;
  embedding: ProcessState;
  indexed: ProcessState;
  lastProcessed: string;
  accessLevel: string;
  chunks: number;
}

export type ModelKind = "reasoning" | "vision" | "code" | "fast" | "embedding";
export interface KModel {
  id: string;
  name: string;
  kind: ModelKind;
  role: string;
  params: string;
  quant: string;
  status: "READY" | "LOADING" | "OFFLINE";
  sizeGb: number;
  ctx: string;
  tokensPerSec: number;
}

export interface RoutingRule {
  taskType: string;
  modelId: string;
  reason: string;
}

export type StepStatus = "pending" | "active" | "done" | "warn";
export interface AgentStep {
  id: string;
  agent: string;
  label: string;
  detail: string;
  status: StepStatus;
  durationMs: number;
  ts?: string;
}

export interface Evidence {
  id: string;
  source: string;
  page: number;
  relevance: number; // 0-100
  excerpt: string;
  tags: string[];
}

export type ReviewState = "auto-approved" | "needs-review" | "approved" | "rejected";
export interface Finding {
  id: string;
  index: number;
  title: string;
  detail: string;
  severity: "info" | "low" | "medium" | "high";
  confidence: number; // 0-100
  verified: boolean;
  reviewState: ReviewState;
  evidenceIds: string[];
  equipment: string[];
}

export interface AgentRun {
  id: string;
  task: string;
  agent: string;
  model: string;
  startTime: string;
  durationMs: number;
  status: "COMPLETED" | "RUNNING" | "QUEUED" | "REVIEW" | "FAILED";
  verification: number; // 0-100
  evidenceBacked: string; // "8/9"
  needsReview: number;
  steps: AgentStep[];
  findingIds: string[];
  deliverableId?: string;
}

export interface Deliverable {
  id: string;
  title: string;
  category: string;
  format: string; // PDF / DOCX / XLSX / TXT
  project: string;
  createdAt: string;
  sizeKb: number;
  confidence: number;
  humanReview: boolean;
  runId?: string;
  sections: string[];
}

export interface AuditEntry {
  ts: string;
  actor: string;
  action: string;
  detail: string;
  level: "info" | "secure" | "warn" | "block";
}

export interface KnowledgeSource {
  name: string;
  count: number;
  chunks: number;
  icon: string;
}

export interface PidRegion {
  id: string; // equipment tag
  label: string;
  kind: "pump" | "valve" | "tank" | "exchanger" | "instrument" | "line";
  // normalized 0-100 box coords on the SVG viewBox
  x: number;
  y: number;
  w: number;
  h: number;
  note: string;
  evidenceId?: string;
}
