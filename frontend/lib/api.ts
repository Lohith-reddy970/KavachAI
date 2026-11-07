const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface HealthResponse {
  status: string;
  mode: string;
  version: string;
}

export interface DocumentPreview {
  id: number;
  filename: string;
  kind: "pdf" | "image" | "text";
  text: string;
  note: string;
  truncated: boolean;
}

export interface SourceReference {
  document_id: number;
  page: number;
  excerpt: string;
  char_start?: number | null;
  char_end?: number | null;
}

export interface EvidencePreview {
  document_id: number;
  filename: string;
  page: number;
  page_label: string;
  text: string;
  highlight_start: number;
  highlight_end: number;
  excerpt: string;
  boxes: { x: number; y: number; width: number; height: number }[];
  has_image: boolean;
  note: string;
  truncated: boolean;
}

export interface ChatResponse {
  answer: string;
  citations: (SourceReference & { number: number; source: string })[];
  status: "cited" | "insufficient_evidence";
  model: string | null;
  provider: string | null;
}

export interface AnalysisBatch {
  id: string;
  status: "queued" | "running" | "completed" | "completed_with_errors";
  created_at: string;
  request: { document_ids: number[]; profile: string; analysis_mode: AnalysisMode; description: string };
  counts: { total: number; pending: number; queued: number; running: number; completed: number; error: number };
  items: { id: number; document_id: number; filename: string; job_id: string; run_id: number | null; status: string; error: string | null }[];
}

export interface KnowledgeSearchResult {
  id: string;
  source: string;
  page: number;
  text: string;
  score: number; // cosine similarity, 0-1
  document_id?: number | null;
  char_start?: number | null;
  char_end?: number | null;
}

export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeSearchResult[];
  total_chunks: number;
  embedding_backend: string;
}

export type AnalysisMode = "risk_review" | "summary" | "extract_fields";

export interface AnalysisProfile {
  id: string;
  name: string;
  description: string;
}

export interface AnalysisCatalog {
  profiles: AnalysisProfile[];
  analysis_modes: { id: AnalysisMode; name: string; description: string }[];
}

export interface LiveRun {
  id: number;
  scenario: string | null;
  status: string; // running | completed | awaiting_review | halted | error
  verification_score: number | null;
  evidence_backed: string;
  started_at: string;
  analysis_mode?: AnalysisMode;
  analysis_profile?: string;
}

export interface LiveFinding {
  id: number;
  title: string;
  severity: string;
  confidence: number;
  equipment_id: string;
  needs_review: number;
  review_status: string; // pending | approved | rejected
  review_reasons?: string[];
  evidence: {
    id: number;
    source: string;
    page: number | null;
    excerpt: string;
    extraction_method?: string;
    ocr_confidence?: number | null;
    location?: {
      char_start?: number;
      char_end?: number;
      bbox?: { x: number; y: number; width: number; height: number; coordinate_space: string };
    } | null;
  }[];
}

export interface LiveRunDetail {
  run: LiveRun;
  steps: { id: number; agent: string; message: string; status: string; detail: string }[];
  findings: LiveFinding[];
  deliverables: { id: number; filename: string; fmt: string }[];
  analysis?: { text: string; model: string; provider: string; meta?: Record<string, unknown> } | null;
  vision?: { text: string; model: string; provider: string; source: string; advisory: boolean } | null;
  extraction?: { page_count: number; ocr_pages: number; method: string; note?: string } | null;
}

export interface AnalysisStage {
  id: string;
  label: string;
  description: string;
  status: "pending" | "running" | "completed" | "warning" | "skipped" | "error" | "not_run";
  message: string;
  detail: string;
  started_at: string | null;
  finished_at: string | null;
  metadata: Record<string, unknown>;
  events: { at: string; status: string; message: string; detail: string }[];
}

export interface AnalysisJob {
  id: string;
  document_id: number;
  document: { id: number; filename: string } | null;
  status: "queued" | "running" | "completed" | "error";
  created_at: string;
  updated_at: string;
  run_id: number | null;
  stages: AnalysisStage[];
  error: string | null;
  request: { document_id: number; profile: string; analysis_mode: AnalysisMode; title: string; description: string; workflow: "pipeline" | "planner" };
  result: { run: LiveRunDetail; document?: unknown } | null;
}

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export interface PlannerStep {
  step: number;
  action: string;
  reason: string;
  status: string; // completed | blocked | rejected
}

export interface AgentRunResponse extends LiveRunDetail {
  planner: {
    provider: string;
    max_steps: number;
    steps_used: number;
    stop_reason: string;
    trace: PlannerStep[];
    requires_human_review: boolean;
  };
}

export interface SandboxStatus {
  status: "ready" | "disabled" | "unavailable";
  available: boolean;
  runtime: string;
  network: string;
  reason: string;
  limits: { timeout_seconds: number; memory_mb: number; output_bytes: number; cpus: number; pids: number };
}

export interface SandboxResult {
  job_id: string;
  status: "completed" | "failed" | "timed_out" | "output_limit";
  stdout: string;
  stderr: string;
  exit_code: number | null;
  duration_ms: number;
  output_truncated: boolean;
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 2500): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, { ...init, signal: ctrl.signal, cache: "no-store" });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`, res.status);
    }
    return (await res.json()) as T;
  } catch (error) {
    if (ctrl.signal.aborted) {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)} seconds; a local model may still be processing.`);
    }
    throw error;
  } finally {
    clearTimeout(t);
  }
}

const get = <T,>(path: string, timeoutMs?: number) => request<T>(path, {}, timeoutMs);

const post = <T,>(path: string, body: unknown, timeoutMs?: number) =>
  request<T>(
    path,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    timeoutMs,
  );

export const api = {
  base: BASE,
  health: () => get<HealthResponse>("/api/health"),
  systemStatus: () => get<any>("/api/system/status", 15000),
  sandboxStatus: () => get<SandboxStatus>("/api/sandbox/status", 15000),
  executeCode: (code: string, stdin: string, timeoutSeconds: number) =>
    request<SandboxResult>("/api/sandbox/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Kavach-Sandbox": "execute" },
      body: JSON.stringify({ code, stdin, timeout_seconds: timeoutSeconds }),
    }, 75000),
  documents: () => get<any>("/api/documents"),
  documentPreview: (id: string) => get<DocumentPreview>(`/api/documents/${encodeURIComponent(id)}/preview`, 15000),
  evidencePreview: (id: number) => get<EvidencePreview>(`/api/evidence/${id}/preview`, 60000),
  sourcePassage: (source: SourceReference) => post<EvidencePreview>(`/api/documents/${source.document_id}/passage`, source, 60000),
  sourcePageUrl: (documentId: number, page: number) => `${BASE}/api/documents/${documentId}/pages/${page}/image`,
  chat: (question: string, documentIds: number[], history: { role: "user" | "assistant"; content: string }[]) =>
    post<ChatResponse>("/api/chat", { question, document_ids: documentIds, history }, 180000),
  startBatch: (documentIds: string[], profile: string, analysisMode: AnalysisMode, description: string, requestId: string) =>
    post<AnalysisBatch>("/api/analysis/batches", { document_ids: documentIds.map(Number), profile, analysis_mode: analysisMode, description, request_id: requestId }, 15000),
  analysisBatches: () => get<AnalysisBatch[]>("/api/analysis/batches", 10000),
  documentContentUrl: (id: string, download = false) =>
    `${BASE}/api/documents/${encodeURIComponent(id)}/content${download ? "?download=true" : ""}`,
  deleteDocument: (id: string) => request<{ id: number; deleted: boolean; history_retained: boolean }>(
    `/api/documents/${encodeURIComponent(id)}`, { method: "DELETE" }, 15000),
  models: () => get<any>("/api/models"),
  profiles: () => get<AnalysisCatalog>("/api/profiles"),
  knowledge: () => get<any>("/api/knowledge"),
  searchKnowledge: (query: string, topK = 4) =>
    post<KnowledgeSearchResponse>("/api/knowledge/search", { query, top_k: topK }),
  runs: () => get<LiveRun[]>("/api/agents/runs"),
  run: (id: number) => get<LiveRunDetail>(`/api/agents/runs/${id}`, 10000),
  startAnalysis: (documentId: string, task: string, profile: string, mode: AnalysisMode, planner: boolean) =>
    post<AnalysisJob>("/api/analysis/jobs", {
      document_id: Number(documentId), title: task.slice(0, 300), description: task,
      profile, analysis_mode: mode, workflow: planner ? "planner" : "pipeline",
    }, 15000),
  analysisJob: (id: string) => get<AnalysisJob>(`/api/analysis/jobs/${encodeURIComponent(id)}`, 10000),
  // The planner can load/switch several local models during one synchronous run.
  agentRun: (task: string, documentId: string, profile: string, analysisMode: AnalysisMode) =>
    post<AgentRunResponse>("/api/agent/run", { task, document_id: Number(documentId), profile, analysis_mode: analysisMode }, 600000),
  reviewFinding: (findingId: number, decision: "approve" | "reject") =>
    post<unknown>(`/api/review/${findingId}/${decision}`, {}, 10000),
  auditLogs: () => get<any>("/api/audit-logs"),
  deliverables: () => get<any>("/api/deliverables"),
  uploadDocument: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ id: number; filename: string; size_bytes: number }>("/api/documents/upload", { method: "POST", body }, 60000);
  },
  analyzeDocument: (
    id: string | number,
    title: string,
    description = "",
    profile = "general",
    analysisMode: AnalysisMode = "risk_review",
  ) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 300000);
    return fetch(`${BASE}/api/documents/${id}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, description, profile, analysis_mode: analysisMode }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (response.ok) return response.json();
        const body = await response.json().catch(() => null);
        const detail = body?.detail;
        const message = typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((item: { msg?: string }) => item.msg ?? "Invalid request").join("; ")
            : `Analysis failed (${response.status})`;
        throw new Error(message);
      })
      .catch((error) => {
        if (controller.signal.aborted) {
          throw new Error("Analysis timed out after 5 minutes. The backend may still finish; check Agent Runs before retrying.");
        }
        throw error;
      })
      .finally(() => clearTimeout(timeout));
  },
};
