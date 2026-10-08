// Optional live-backend client.
//
// The UI runs standalone on the bundled sample data (lib/data.ts). When the
// FastAPI backend is running, these helpers let the same components read live
// endpoints instead — the contract
// (paths + shapes) is identical, so swapping the source is a one-line change.

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface HealthResponse {
  status: string;
  mode: string;
  version: string;
}

export interface KnowledgeSearchResult {
  id: string;
  source: string;
  page: number;
  text: string;
  score: number; // cosine similarity, 0-1
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
}

export interface LiveFinding {
  id: number;
  title: string;
  severity: string;
  confidence: number;
  equipment_id: string;
  needs_review: number;
  review_status: string; // pending | approved | rejected
  evidence: { id: number; source: string; page: number | null; excerpt: string }[];
}

export interface LiveRunDetail {
  run: LiveRun;
  steps: { id: number; agent: string; message: string; status: string; detail: string }[];
  findings: LiveFinding[];
  deliverables: { id: number; filename: string; fmt: string }[];
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

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 2500): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, { ...init, signal: ctrl.signal, cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
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
  systemStatus: () => get<any>("/api/system/status"),
  documents: () => get<any>("/api/documents"),
  models: () => get<any>("/api/models"),
  profiles: () => get<AnalysisCatalog>("/api/profiles"),
  knowledge: () => get<any>("/api/knowledge"),
  searchKnowledge: (query: string, topK = 4) =>
    post<KnowledgeSearchResponse>("/api/knowledge/search", { query, top_k: topK }),
  runs: () => get<LiveRun[]>("/api/agents/runs"),
  run: (id: number) => get<LiveRunDetail>(`/api/agents/runs/${id}`, 10000),
  // The planner can load/switch several local models during one synchronous run.
  agentRun: (task: string) => post<AgentRunResponse>("/api/agent/run", { task }, 600000),
  reviewFinding: (findingId: number, decision: "approve" | "reject") =>
    post<unknown>(`/api/review/${findingId}/${decision}`, {}, 10000),
  auditLogs: () => get<any>("/api/audit-logs"),
  deliverables: () => get<any>("/api/deliverables"),
  runDemo: () =>
    fetch(`${BASE}/api/demo/run`, { method: "POST" }).then((r) => r.json()),
  uploadDocument: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return fetch(`${BASE}/api/documents/upload`, { method: "POST", body }).then((r) => {
      if (!r.ok) throw new Error(`Upload failed (${r.status})`);
      return r.json();
    });
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
