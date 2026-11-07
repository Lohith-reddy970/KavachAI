"use client";

// Backend data with explicit loading and unavailable states.

import { useEffect, useState } from "react";
import { api, type AnalysisCatalog } from "./api";
import type { AuditEntry, Deliverable, KDocument } from "./types";

export type Source = "loading" | "unavailable" | "live";

export function useLive<T>(fetcher: () => Promise<T>, empty: T) {
  const [data, setData] = useState<T>(empty);
  const [source, setSource] = useState<Source>("loading");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const live = await fetcher();
        if (!alive) return;
        setData(live);
        setSource("live");
      } catch (err) {
        if (alive) {
          setSource("unavailable");
          setError(err instanceof Error ? err.message : "Backend unavailable");
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { data, source, loading, error };
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
    const indexed = d.status === "ready" || d.status === "indexed";
    const extracted = indexed || d.status === "analyzed" || Boolean(d.extraction_method);
    const extractionFailed = d.status === "needs_ocr" || d.status === "unreadable";
    return {
      id: String(d.id),
      name: d.filename ?? d.name,
      type: extType(d.filename ?? d.name ?? ""),
      sizeBytes: d.size_bytes ?? 0,
      pages: d.pages ?? 0,
      classification: classify(d.doc_type ?? ""),
      ocr: extractionFailed ? "error" : extracted ? "done" : "pending",
      embedding: indexed ? "done" : "pending",
      indexed: indexed ? "done" : "pending",
      lastProcessed: (d.created_at ?? "").replace("T", " ").slice(0, 16),
      accessLevel: "Local",
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
    category: d.fmt === "xlsx" ? "Fields & Findings" : d.fmt === "docx" ? "Review Note" : "Document Report",
    format: (d.fmt ?? "txt").toUpperCase(),
    project: d.run_id ? `Analysis run #${d.run_id}` : "Local document analysis",
    createdAt: (d.created_at ?? "").replace("T", " ").slice(0, 16),
    sizeKb: Math.max(1, Math.round((d.size_bytes ?? 0) / 1024)),
    runId: d.run_id ? `RUN-${d.run_id}` : undefined,
    sections: [],
    downloadUrl: `${api.base}/api/deliverables/${d.id}/download`,
  }));
}

export type MetricSource = "hardware" | "unavailable";

export interface LiveSystem {
  gpu: number | null;
  vramUsedPct: number | null;
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
    ...(s.models?.list ?? []).map((m: any) => ({ name: m.name, detail: "configured model", status: (m.status ?? "unknown").toUpperCase() })),
    { name: "Vector DB", detail: s.vector_db?.backend ?? "vector", status: (s.vector_db?.status ?? "online").toUpperCase() },
    {
      name: "OCR Engine",
      detail: s.ocr?.reason ? `${s.ocr.engine}: ${s.ocr.reason}` : s.ocr?.engine ?? "ocr",
      status: (s.ocr?.status ?? "online").toUpperCase(),
    },
    { name: "Sandbox", detail: s.sandbox?.reason ?? "unavailable", status: (s.sandbox?.status ?? "unavailable").toUpperCase() },
    { name: "Provider policy", detail: s.network ?? "unavailable", status: (s.mode ?? "unknown").toUpperCase() },
  ];
  const vramUsed = metric(s.gpu?.memory_used_gb);
  const vramTotal = metric(s.gpu?.memory_total_gb);
  return {
    gpu: metric(s.gpu?.utilization_pct),
    vramUsedPct: metric(s.gpu?.memory_used_pct),
    gpuName: typeof s.gpu?.device === "string" ? s.gpu.device : undefined,
    vramUsedGb: vramUsed ?? undefined,
    vramTotalGb: vramTotal ?? undefined,
    gpuTempC: metric(s.gpu?.temperature_c) ?? undefined,
    cpuPct: metric(s.cpu?.utilization_pct),
    ramPct: metric(s.ram?.utilization_pct),
    gpuSource: s.gpu?.source === "hardware" ? "hardware" : "unavailable",
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
