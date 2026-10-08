// KAVACH AI — bundled, deterministic sample dataset.
// The UI runs standalone on this data, with or without the FastAPI backend.
// Everything here is FICTIONAL sample content.
// Facility: KAVACH DEMO REFINERY · Unit 4.

import type {
  AgentRun,
  AuditEntry,
  Deliverable,
  Evidence,
  Finding,
  KDocument,
  KModel,
  KnowledgeSource,
  PidRegion,
  RoutingRule,
} from "./types";

export const FACILITY = "KAVACH DEMO REFINERY";
export const UNIT = "Unit 4 — Crude Distillation";

export const documents: KDocument[] = [
  {
    id: "doc-pid",
    name: "Unit_4_Plant_PID.pdf",
    type: "PDF",
    sizeBytes: 2_418_000,
    pages: 3,
    classification: "CONFIDENTIAL",
    ocr: "done",
    embedding: "done",
    indexed: "done",
    lastProcessed: "2026-09-04 17:42",
    accessLevel: "Eng-L2",
    chunks: 214,
  },
  {
    id: "doc-insp",
    name: "Inspection_Report_2026.pdf",
    type: "PDF",
    sizeBytes: 986_000,
    pages: 12,
    classification: "CONFIDENTIAL",
    ocr: "done",
    embedding: "done",
    indexed: "done",
    lastProcessed: "2026-09-04 17:42",
    accessLevel: "Eng-L2",
    chunks: 168,
  },
  {
    id: "doc-manual",
    name: "Equipment_Manual.pdf",
    type: "PDF",
    sizeBytes: 5_140_000,
    pages: 58,
    classification: "INTERNAL",
    ocr: "done",
    embedding: "done",
    indexed: "done",
    lastProcessed: "2026-09-04 17:41",
    accessLevel: "Eng-L1",
    chunks: 742,
  },
  {
    id: "doc-calc",
    name: "Engineering_Calculation.pdf",
    type: "PDF",
    sizeBytes: 612_000,
    pages: 7,
    classification: "CONFIDENTIAL",
    ocr: "done",
    embedding: "done",
    indexed: "done",
    lastProcessed: "2026-09-04 17:40",
    accessLevel: "Eng-L2",
    chunks: 96,
  },
  {
    id: "doc-code",
    name: "sample_internal_code.py",
    type: "PY",
    sizeBytes: 8_200,
    pages: 1,
    classification: "RESTRICTED",
    ocr: "done",
    embedding: "done",
    indexed: "done",
    lastProcessed: "2026-09-04 17:39",
    accessLevel: "Dev-L2",
    chunks: 14,
  },
];

export const models: KModel[] = [
  {
    id: "qwen3-8b",
    name: "qwen3:8b",
    kind: "reasoning",
    role: "Reasoning / evidence synthesis",
    params: "8.2B",
    quant: "Q4_K_M",
    status: "READY",
    sizeGb: 5.2,
    ctx: "40K max",
    tokensPerSec: 0,
  },
  {
    id: "llava-7b",
    name: "llava:7b",
    kind: "vision",
    role: "P&ID / image analysis",
    params: "7.0B",
    quant: "Q4_0",
    status: "READY",
    sizeGb: 4.7,
    ctx: "32K max",
    tokensPerSec: 0,
  },
  {
    id: "llama3-2-3b",
    name: "llama3.2:3b",
    kind: "fast",
    role: "Code, classification, extraction, and other text tasks",
    params: "3.2B",
    quant: "Q4_K_M",
    status: "READY",
    sizeGb: 2.0,
    ctx: "128K max",
    tokensPerSec: 0,
  },
  {
    id: "nomic-embed-text",
    name: "nomic-embed-text:latest",
    kind: "embedding",
    role: "Document embeddings (RAG)",
    params: "137M",
    quant: "FP16",
    status: "READY",
    sizeGb: 0.3,
    ctx: "2K model context",
    tokensPerSec: 0,
  },
];

export const routingRules: RoutingRule[] = [
  { taskType: "P&ID / Diagram Analysis", modelId: "llava-7b", reason: "Visual input requires a vision model" },
  { taskType: "Industrial Document Analysis", modelId: "qwen3-8b", reason: "Evidence synthesis and reasoning" },
  { taskType: "Code Generation / Review", modelId: "llama3-2-3b", reason: "Configured general-purpose model for other tasks" },
  { taskType: "Document Summarization", modelId: "llama3-2-3b", reason: "Configured general-purpose model for other text tasks" },
  { taskType: "Classification / Extraction", modelId: "llama3-2-3b", reason: "Configured smaller model for routine text tasks" },
  { taskType: "Semantic Retrieval", modelId: "nomic-embed-text", reason: "Dedicated local embedding model" },
];

export const knowledgeSources: KnowledgeSource[] = [
  { name: "Engineering Documents", count: 9, chunks: 1204, icon: "FileText" },
  { name: "Inspection Reports", count: 6, chunks: 812, icon: "ClipboardCheck" },
  { name: "Equipment Manuals", count: 4, chunks: 968, icon: "BookOpen" },
  { name: "P&IDs", count: 3, chunks: 341, icon: "Workflow" },
  { name: "Internal SOPs", count: 2, chunks: 157, icon: "ShieldCheck" },
];

export const knowledgeStats = {
  documentsIndexed: 24,
  chunks: 3482,
  embeddings: "Ready",
  vectorDb: "ONLINE",
  model: "nomic-embed-text · F16",
  dimensions: 768,
};

export const evidence: Evidence[] = [
  {
    id: "ev-1",
    source: "Inspection_Report_2026.pdf",
    page: 7,
    relevance: 96,
    excerpt:
      "Minor corrosion observed near the outlet section of pump P-101. Wall-thickness reading 6.1 mm against a design minimum of 6.4 mm. Recommend re-gauging at next turnaround.",
    tags: ["P-101"],
  },
  {
    id: "ev-2",
    source: "Equipment_Manual.pdf",
    page: 42,
    relevance: 91,
    excerpt:
      "P-101 / P-102 centrifugal pumps: minimum allowable outlet-nozzle wall thickness is 6.4 mm. Below this value the nozzle must be scheduled for repair or replacement.",
    tags: ["P-101", "P-102"],
  },
  {
    id: "ev-3",
    source: "Inspection_Report_2026.pdf",
    page: 9,
    relevance: 88,
    excerpt:
      "Relief valve V-204 set pressure verified at 14.2 bar. Last bench test 2025-11. Within the 24-month re-certification interval.",
    tags: ["V-204"],
  },
  {
    id: "ev-4",
    source: "Engineering_Calculation.pdf",
    page: 3,
    relevance: 90,
    excerpt:
      "T-101 design pressure 3.5 bar(g); calculated corrosion allowance consumed = 41% after 8 years of service. Remaining life estimate 11 years at current rate.",
    tags: ["T-101"],
  },
  {
    id: "ev-5",
    source: "Inspection_Report_2026.pdf",
    page: 5,
    relevance: 84,
    excerpt:
      "Heat exchanger HX-301 shows fouling on the shell side; approach temperature increased by 6°C versus baseline. Clean at next opportunity.",
    tags: ["HX-301"],
  },
  {
    id: "ev-6",
    source: "Equipment_Manual.pdf",
    page: 17,
    relevance: 79,
    excerpt:
      "HX-301 shell-and-tube exchanger: recommended cleaning threshold is a 5°C rise in approach temperature above commissioning baseline.",
    tags: ["HX-301"],
  },
  {
    id: "ev-7",
    source: "Inspection_Report_2026.pdf",
    page: 11,
    relevance: 74,
    excerpt:
      "Instrument loop PT-104 on T-101 reads 0.2 bar high against the field gauge. Flagged for calibration; not safety-critical.",
    tags: ["T-101", "PT-104"],
  },
  {
    id: "ev-8",
    source: "Engineering_Calculation.pdf",
    page: 5,
    relevance: 81,
    excerpt:
      "Pump P-102 vibration trend within ISO 10816 Zone B. No action required this cycle.",
    tags: ["P-102"],
  },
];

export const findings: Finding[] = [
  {
    id: "f-1",
    index: 1,
    title: "Wall-thickness at P-101 outlet below design minimum",
    detail:
      "Measured wall thickness 6.1 mm at the P-101 outlet nozzle is below the 6.4 mm minimum stated in the equipment manual. Corrosion progression is credible and should be scheduled for repair at the next turnaround.",
    severity: "high",
    confidence: 94,
    verified: true,
    reviewState: "needs-review",
    evidenceIds: ["ev-1", "ev-2"],
    equipment: ["P-101"],
  },
  {
    id: "f-2",
    index: 2,
    title: "Potential corrosion indication around P-101 outlet",
    detail:
      "Visual inspection notes minor corrosion near the P-101 outlet section. Consistent with the wall-thickness reading. Confidence is moderate pending re-gauging.",
    severity: "medium",
    confidence: 82,
    verified: true,
    reviewState: "needs-review",
    evidenceIds: ["ev-1"],
    equipment: ["P-101"],
  },
  {
    id: "f-3",
    index: 3,
    title: "HX-301 shell-side fouling exceeds cleaning threshold",
    detail:
      "Approach-temperature rise of 6°C exceeds the 5°C manual threshold for HX-301. Schedule shell-side cleaning at next opportunity to recover thermal duty.",
    severity: "medium",
    confidence: 89,
    verified: true,
    reviewState: "auto-approved",
    evidenceIds: ["ev-5", "ev-6"],
    equipment: ["HX-301"],
  },
  {
    id: "f-4",
    index: 4,
    title: "T-101 corrosion allowance 41% consumed",
    detail:
      "Calculated corrosion allowance for tank T-101 is 41% consumed after 8 years. Remaining-life estimate 11 years at current rate. No immediate action; continue monitoring.",
    severity: "low",
    confidence: 90,
    verified: true,
    reviewState: "auto-approved",
    evidenceIds: ["ev-4"],
    equipment: ["T-101"],
  },
  {
    id: "f-5",
    index: 5,
    title: "Relief valve V-204 within certification interval",
    detail:
      "V-204 set pressure verified at 14.2 bar; last bench test within the 24-month interval. No action required.",
    severity: "info",
    confidence: 96,
    verified: true,
    reviewState: "auto-approved",
    evidenceIds: ["ev-3"],
    equipment: ["V-204"],
  },
  {
    id: "f-6",
    index: 6,
    title: "PT-104 instrument drift on T-101",
    detail:
      "Pressure transmitter PT-104 reads 0.2 bar high versus field gauge. Flag for calibration. Not safety-critical.",
    severity: "low",
    confidence: 85,
    verified: true,
    reviewState: "auto-approved",
    evidenceIds: ["ev-7"],
    equipment: ["T-101", "PT-104"],
  },
  {
    id: "f-7",
    index: 7,
    title: "P-102 vibration within acceptable band",
    detail:
      "Pump P-102 vibration trend sits within ISO 10816 Zone B. No action this cycle.",
    severity: "info",
    confidence: 92,
    verified: true,
    reviewState: "auto-approved",
    evidenceIds: ["ev-8"],
    equipment: ["P-102"],
  },
  {
    id: "f-8",
    index: 8,
    title: "P-101 / P-102 outlet spec cross-reference confirmed",
    detail:
      "Equipment manual outlet-nozzle spec (6.4 mm min) matched to both P-101 and P-102 by tag. Cross-reference used to grade finding #1.",
    severity: "info",
    confidence: 93,
    verified: true,
    reviewState: "auto-approved",
    evidenceIds: ["ev-2"],
    equipment: ["P-101", "P-102"],
  },
  {
    id: "f-9",
    index: 9,
    title: "Fouling root-cause attribution (unverified)",
    detail:
      "Model hypothesises HX-301 fouling is driven by crude feed quality change. No supporting evidence found in the indexed corpus — surfaced for reviewer judgment rather than asserted.",
    severity: "low",
    confidence: 58,
    verified: false,
    reviewState: "needs-review",
    evidenceIds: [],
    equipment: ["HX-301"],
  },
];

export const pidRegions: PidRegion[] = [
  { id: "T-101", label: "Feed Tank", kind: "tank", x: 6, y: 30, w: 15, h: 34, note: "Crude feed surge tank", evidenceId: "ev-4" },
  { id: "P-101", label: "Charge Pump", kind: "pump", x: 30, y: 56, w: 9, h: 14, note: "Corrosion flagged at outlet", evidenceId: "ev-1" },
  { id: "P-102", label: "Standby Pump", kind: "pump", x: 30, y: 74, w: 9, h: 14, note: "Vibration nominal", evidenceId: "ev-8" },
  { id: "HX-301", label: "Feed/Effluent Exchanger", kind: "exchanger", x: 50, y: 40, w: 18, h: 16, note: "Shell-side fouling", evidenceId: "ev-5" },
  { id: "V-204", label: "Relief Valve", kind: "valve", x: 74, y: 20, w: 8, h: 10, note: "Set 14.2 bar — certified", evidenceId: "ev-3" },
  { id: "PT-104", label: "Pressure Xmtr", kind: "instrument", x: 20, y: 16, w: 7, h: 7, note: "Calibration drift 0.2 bar", evidenceId: "ev-7" },
];

// ---- Agent runs -----------------------------------------------------------

export const SAMPLE_TASK =
  "Review the selected document for risks and cite supporting evidence.";

export const primaryRunSteps = [
  { id: "s0", agent: "Security Agent", label: "Policy & classification check", detail: "3 CONFIDENTIAL docs · airgapped policy satisfied · 0 external calls", durationMs: 900 },
  { id: "s1", agent: "Router Agent", label: "Task classification", detail: "Industrial Document Analysis (multimodal)", durationMs: 1100 },
  { id: "s2", agent: "Model Router", label: "Model routing", detail: "llava:7b (vision) + qwen3:8b (reasoning) + llama3.2:3b (other)", durationMs: 800 },
  { id: "s3", agent: "Planner", label: "Execution plan created", detail: "6 steps · document → vision → RAG → reason → verify → deliver", durationMs: 1000 },
  { id: "s4", agent: "Document Agent", label: "OCR & text extraction", detail: "Inspection_Report_2026.pdf · 12 pages · OCR completed", durationMs: 2600 },
  { id: "s5", agent: "Vision Agent", label: "P&ID regions detected", detail: "6 regions · P-101, P-102, V-204, T-101, HX-301, PT-104", durationMs: 2400 },
  { id: "s6", agent: "Knowledge Agent", label: "Knowledge retrieved", detail: "8 evidence chunks · avg relevance 85%", durationMs: 1800 },
  { id: "s7", agent: "Reasoning Agent", label: "Findings generated", detail: "9 findings graded across 6 equipment tags", durationMs: 2200 },
  { id: "s8", agent: "Verification Agent", label: "Evidence cross-check completed", detail: "8/9 evidence-backed · verification 94%", durationMs: 1700 },
  { id: "s9", agent: "Deliverable Agent", label: "Report generated", detail: "Engineering Review Report · 1 finding flagged for human review", durationMs: 1500 },
];

export const runs: AgentRun[] = [
  {
    id: "RUN-2026-0912",
    task: "Inspection Report vs P&ID — Engineering Review",
    agent: "Industrial Document Analyst",
    model: "llava:7b + qwen3:8b",
    startTime: "2026-09-04 17:42:22",
    durationMs: 30800,
    status: "REVIEW",
    verification: 94,
    evidenceBacked: "8/9",
    needsReview: 1,
    steps: primaryRunSteps.map((s) => ({ ...s, status: "done" as const })),
    findingIds: findings.map((f) => f.id),
    deliverableId: "del-1",
  },
  {
    id: "RUN-2026-0911",
    task: "Summarize vendor negotiation notes (Q3)",
    agent: "Document Summarizer",
    model: "llama3.2:3b",
    startTime: "2026-09-04 16:18:04",
    durationMs: 6400,
    status: "COMPLETED",
    verification: 97,
    evidenceBacked: "5/5",
    needsReview: 0,
    steps: [],
    findingIds: [],
    deliverableId: "del-2",
  },
  {
    id: "RUN-2026-0910",
    task: "Refactor internal tag-parser utility",
    agent: "Code Assistant",
    model: "llama3.2:3b",
    startTime: "2026-09-04 15:02:51",
    durationMs: 9100,
    status: "COMPLETED",
    verification: 91,
    evidenceBacked: "n/a",
    needsReview: 0,
    steps: [],
    findingIds: [],
    deliverableId: "del-3",
  },
  {
    id: "RUN-2026-0909",
    task: "Board deck: Unit 4 turnaround readiness",
    agent: "Presentation Builder",
    model: "qwen3:8b",
    startTime: "2026-09-04 11:44:12",
    durationMs: 12400,
    status: "COMPLETED",
    verification: 95,
    evidenceBacked: "7/7",
    needsReview: 0,
    steps: [],
    findingIds: [],
    deliverableId: "del-4",
  },
];

export const deliverables: Deliverable[] = [
  {
    id: "del-1",
    title: "Engineering Review Report — Unit 4 Inspection",
    category: "Engineering Report",
    format: "PDF",
    project: "Unit 4 Inspection",
    createdAt: "2026-09-04 17:42",
    sizeKb: 214,
    confidence: 94,
    humanReview: true,
    runId: "RUN-2026-0912",
    sections: [
      "Executive Summary",
      "Findings",
      "Equipment Analysis",
      "Evidence",
      "Risk Indicators",
      "Recommendations",
      "Verification",
    ],
  },
  {
    id: "del-2",
    title: "Vendor Negotiation Summary — Q3",
    category: "Approval Note",
    format: "DOCX",
    project: "Procurement",
    createdAt: "2026-09-04 16:18",
    sizeKb: 68,
    confidence: 97,
    humanReview: false,
    runId: "RUN-2026-0911",
    sections: ["Summary", "Key Terms", "Recommended Position"],
  },
  {
    id: "del-3",
    title: "tag_parser.py — Refactored + Tests",
    category: "Code",
    format: "TXT",
    project: "Internal Tooling",
    createdAt: "2026-09-04 15:03",
    sizeKb: 12,
    confidence: 91,
    humanReview: false,
    runId: "RUN-2026-0910",
    sections: ["Diff", "Unit Tests", "Notes"],
  },
  {
    id: "del-4",
    title: "Unit 4 Turnaround Readiness — Board Deck",
    category: "Management Presentation",
    format: "PDF",
    project: "Unit 4 Inspection",
    createdAt: "2026-09-04 11:44",
    sizeKb: 1240,
    confidence: 95,
    humanReview: false,
    runId: "RUN-2026-0909",
    sections: ["Overview", "Status", "Risks", "Recommendation"],
  },
  {
    id: "del-5",
    title: "Corrosion Trend Analysis — Unit 4 Pumps",
    category: "Excel Analysis",
    format: "XLSX",
    project: "Unit 4 Inspection",
    createdAt: "2026-09-04 17:44",
    sizeKb: 41,
    confidence: 90,
    humanReview: false,
    runId: "RUN-2026-0912",
    sections: ["Readings", "Trend", "Projection"],
  },
];

export const auditLog: AuditEntry[] = [
  { ts: "17:42:11", actor: "eng.review", action: "Document uploaded", detail: "Inspection_Report_2026.pdf (986 KB)", level: "secure" },
  { ts: "17:42:12", actor: "security-agent", action: "Classification set", detail: "CONFIDENTIAL · access Eng-L2", level: "secure" },
  { ts: "17:42:13", actor: "document-agent", action: "OCR executed locally", detail: "Tesseract · 12 pages · no network", level: "info" },
  { ts: "17:42:15", actor: "policy", action: "External call blocked", detail: "egress denied by airgapped policy", level: "block" },
  { ts: "17:42:17", actor: "knowledge-agent", action: "Document indexed", detail: "168 chunks · nomic-embed-text embeddings", level: "info" },
  { ts: "17:42:22", actor: "router-agent", action: "Agent run started", detail: "RUN-2026-0912", level: "info" },
  { ts: "17:42:25", actor: "model-router", action: "Model selected", detail: "llava:7b (vision) + qwen3:8b (reasoning)", level: "info" },
  { ts: "17:42:41", actor: "knowledge-agent", action: "Evidence retrieved", detail: "8 chunks · avg relevance 85%", level: "info" },
  { ts: "17:42:48", actor: "verification-agent", action: "Verification completed", detail: "8/9 evidence-backed · 94%", level: "secure" },
  { ts: "17:42:52", actor: "deliverable-agent", action: "Report generated", detail: "Engineering Review Report (PDF)", level: "info" },
  { ts: "17:42:52", actor: "policy", action: "Data residency confirmed", detail: "0 bytes left the environment", level: "secure" },
];

export const systemStatus = {
  gpu: 78,
  gpuModel: "NVIDIA RTX A6000 · 48 GB",
  vramUsed: 21.1,
  vramTotal: 48,
  cpu: 34,
  ram: 62,
  services: [
    { name: "qwen3:8b", detail: "reasoning", status: "ONLINE" as const },
    { name: "llava:7b", detail: "vision", status: "ONLINE" as const },
    { name: "llama3.2:3b", detail: "other tasks", status: "ONLINE" as const },
    { name: "nomic-embed-text", detail: "embeddings", status: "ONLINE" as const },
    { name: "Vector DB", detail: "chroma", status: "ONLINE" as const },
    { name: "OCR Engine", detail: "tesseract", status: "ONLINE" as const },
    { name: "Sandbox", detail: "gVisor", status: "SECURE" as const },
    { name: "Network", detail: "egress off", status: "AIR-GAPPED" as const },
  ],
};

export const securityControls = [
  { name: "Air-Gapped", state: "ACTIVE", good: true },
  { name: "External API", state: "BLOCKED", good: true },
  { name: "Internet Access", state: "DISABLED", good: true },
  { name: "Data Residency", state: "ON-PREMISE", good: true },
  { name: "Encryption at Rest", state: "ACTIVE", good: true },
  { name: "Audit Logging", state: "ACTIVE", good: true },
  { name: "RBAC", state: "ACTIVE", good: true },
  { name: "Sandbox Isolation", state: "ACTIVE", good: true },
];

export const overviewMetrics = {
  documentsProcessed: 24,
  tasksExecuted: 187,
  localInference: "100%",
  externalTransfers: 0,
  verificationRate: 94,
};

// Small helpers ------------------------------------------------------------
export function getEvidence(ids: string[]): Evidence[] {
  return ids.map((id) => evidence.find((e) => e.id === id)).filter(Boolean) as Evidence[];
}
export function getFinding(id: string): Finding | undefined {
  return findings.find((f) => f.id === id);
}
export function getRun(id: string): AgentRun | undefined {
  return runs.find((r) => r.id === id);
}
export function modelById(id: string): KModel | undefined {
  return models.find((m) => m.id === id);
}
export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
