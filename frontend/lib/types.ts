// Shared display types for actual backend records.

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

export interface Evidence {
  id: string;
  source: string;
  page: number;
  relevance: number; // 0-100
  excerpt: string;
  tags: string[];
}

export interface Deliverable {
  id: string;
  title: string;
  category: string;
  format: string; // PDF / DOCX / XLSX / TXT
  project: string;
  createdAt: string;
  sizeKb: number;
  confidence?: number;
  humanReview?: boolean;
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
