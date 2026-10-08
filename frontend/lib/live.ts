"use client";

// Live-backend data layer.
//
// Design: the UI renders the bundled sample dataset instantly (so it works offline
// and remains deterministic), then — if the FastAPI backend is
// reachable — transparently swaps in live data and flips the source to "live".
// If the backend is down, everything stays on the curated local data. The
// headline Workbench run stays client-driven regardless, so timing never
// depends on the network.

import { useEffect, useState } from "react";
import { api, type AnalysisCatalog } from "./api";
import type { AuditEntry, Deliverable, KDocument } from "./types";

export type Source = "mock" | "live";

export function useLive<T>(fetcher: () => Promise<T>, fallback: T) {
  const [data, setData] = useState<T>(fallback);
  const [source, setSource] = useState<Source>("mock");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const live = await fetcher();
        if (!alive) return;
        setData(live);
        setSource("live");
      } catch {
        // backend offline — keep the curated fallback
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { data, source, loading };
}

// ---- Normalisers: backend response shapes → frontend domain types ----------

const extType = (filename: string) => (filename.split(".").pop() || "").toUpperCase();

function classify(docType: string): KDocument["classification"] {
  if (docType === "code") return "RESTRICTED";
  if (docType === "manual") return "INTERNAL";
  return "CONFIDENTIAL";
}

export async function fetchDocuments(): Promise<KDocument[]> {
  const raw = await api.documents();
  const arr = Array.isArray(raw) ? raw : raw.documents ?? [];
  return arr.map((d: any): KDocument => {
    const ready = d.status === "ready" || d.status === "indexed";
    return {
      id: String(d.id),
      name: d.filename ?? d.name,
      type: extType(d.filename ?? d.name ?? ""),
      sizeBytes: d.size_bytes ?? 0,
      pages: d.pages ?? 1,
      classification: classify(d.doc_type ?? ""),
      ocr: ready ? "done" : "running",
      embedding: ready ? "done" : "pending",
      indexed: ready ? "done" : "pending",
      lastProcessed: (d.created_at ?? "").replace("T", " ").slice(0, 16),
      accessLevel: d.doc_type === "code" ? "Dev-L2" : "Eng-L2",
      chunks: d.chunks ?? 0,
    };
  });
}

export function fetchAnalysisCatalog(): Promise<AnalysisCatalog> {
  return api.profiles();
}

export async function fetchAuditLogs(): Promise<AuditEntry[]> {
  const raw = await api.auditLogs();
  const arr = Array.isArray(raw) ? raw : raw.logs ?? [];
  return arr.map((a: any): AuditEntry => {
    const t = (a.created_at ?? "").slice(11, 19) || "--:--:--";
    const level: AuditEntry["level"] =
      a.outcome === "blocked" || /block|deny|denied/i.test(a.action + a.detail)
        ? "block"
        : /startup|verification|residency|classification/i.test(a.action)
          ? "secure"
          : "info";
    return { ts: t, actor: a.actor ?? "system", action: a.action ?? "", detail: a.detail ?? "", level };
  });
}

export interface LiveDeliverable extends Deliverable {
  downloadUrl?: string;
}

export async function fetchDeliverables(): Promise<LiveDeliverable[]> {
  const raw = await api.deliverables();
  const arr = Array.isArray(raw) ? raw : raw.deliverables ?? [];
  return arr.map((d: any): LiveDeliverable => ({
    id: String(d.id),
    title: d.name ?? d.filename,
    category: d.fmt === "xlsx" ? "Excel Analysis" : d.fmt === "docx" ? "Review Note" : "Document Analysis Report",
    format: (d.fmt ?? "txt").toUpperCase(),
    project: "Unit 4 Inspection",
    createdAt: (d.created_at ?? "").replace("T", " ").slice(0, 16),
    sizeKb: Math.max(1, Math.round((d.size_bytes ?? 0) / 1024)),
    confidence: 94,
    humanReview: d.fmt === "pdf",
    runId: d.run_id ? `RUN-${d.run_id}` : undefined,
    sections: [],
    downloadUrl: `${api.base}/api/deliverables/${d.id}/download`,
  }));
}

export type MetricSource = "hardware" | "simulated" | "unavailable";

export interface LiveSystem {
  gpu: number;
  vramUsedPct: number;
  gpuName?: string;
  vramUsedGb?: number;
  vramTotalGb?: number;
  gpuTempC?: number;
  cpuPct: number | null;
  ramPct: number | null;
  gpuSource: MetricSource;
  services: { name: string; detail: string; status: string }[];
}

const metric = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

export async function fetchSystem(): Promise<LiveSystem> {
  const s = await api.systemStatus();
  const services = [
    ...(s.models?.list ?? []).map((m: any) => ({ name: m.name, detail: "model", status: (m.status ?? "online").toUpperCase() })),
    { name: "Vector DB", detail: s.vector_db?.backend ?? "vector", status: (s.vector_db?.status ?? "online").toUpperCase() },
    { name: "OCR Engine", detail: s.ocr?.engine ?? "ocr", status: (s.ocr?.status ?? "online").toUpperCase() },
    { name: "Sandbox", detail: s.sandbox?.network ?? "isolated", status: s.sandbox?.status ?? "ISOLATED" },
    { name: "Network", detail: "egress off", status: "AIR-GAPPED" },
  ];
  const vramUsed = metric(s.gpu?.memory_used_gb);
  const vramTotal = metric(s.gpu?.memory_total_gb);
  return {
    gpu: Math.round(metric(s.gpu?.utilization_pct) ?? 0),
    vramUsedPct: Math.round(metric(s.gpu?.memory_used_pct) ?? 0),
    gpuName: typeof s.gpu?.device === "string" ? s.gpu.device : undefined,
    vramUsedGb: vramUsed ?? undefined,
    vramTotalGb: vramTotal ?? undefined,
    gpuTempC: metric(s.gpu?.temperature_c) ?? undefined,
    cpuPct: metric(s.cpu?.utilization_pct),
    ramPct: metric(s.ram?.utilization_pct),
    gpuSource: s.gpu?.source === "hardware" ? "hardware" : "simulated",
    services,
  };
}

/** Polls the local backend for live system metrics; returns null when offline. */
export function usePolledSystem(intervalMs = 5000) {
  const [data, setData] = useState<LiveSystem | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => {
      fetchSystem()
        .then((value) => {
          if (alive) setData(value);
        })
        .catch(() => {
          if (alive) setData(null);
        });
    };
    load();
    const id = setInterval(load, intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [intervalMs]);
  return data;
}
