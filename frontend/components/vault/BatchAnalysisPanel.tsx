"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, type AnalysisBatch, type AnalysisMode } from "@/lib/api";
import { Panel, PanelHeader, StatusPill } from "@/components/ui";

export function BatchAnalysisPanel({ selectedIds, profile, mode, onStarted }: {
  selectedIds: string[]; profile: string; mode: AnalysisMode; onStarted: () => void;
}) {
  const [batches, setBatches] = useState<AnalysisBatch[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const lock = useRef(false);
  const request = useRef<{ signature: string; id: string } | null>(null);
  const refresh = useRef<() => void>(() => {});

  useEffect(() => {
    let alive = true;
    let generation = 0;
    let timer: ReturnType<typeof setTimeout>;
    async function poll(epoch = generation) {
      try {
        const items = await api.analysisBatches();
        if (!alive || epoch !== generation) return;
        setBatches(items); setLoadError(null); setLoading(false);
        setActiveId((current) => current ?? items[0]?.id ?? null);
      } catch (err) {
        if (alive && epoch === generation) { setLoadError(err instanceof Error ? err.message : "Batch history is unavailable."); setLoading(false); }
      } finally {
        if (alive && epoch === generation) timer = setTimeout(() => void poll(epoch), 2000);
      }
    }
    refresh.current = () => { generation++; clearTimeout(timer); void poll(generation); };
    void poll();
    return () => { alive = false; clearTimeout(timer); };
  }, []);

  async function start() {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(null);
    const description = mode === "summary" ? "Summarize this document's purpose, key points, decisions, and open questions."
      : mode === "extract_fields" ? "Extract dates, amounts, contacts, owners, reference IDs, and measurements with exact source excerpts."
        : "Review this document for risks and support each finding with source evidence.";
    const signature = JSON.stringify([selectedIds, profile, mode, description]);
    if (request.current?.signature !== signature) request.current = { signature, id: crypto.randomUUID() };
    try {
      const batch = await api.startBatch(selectedIds, profile, mode, description, request.current.id);
      setActiveId(batch.id); setBatches((items) => [batch, ...items.filter((item) => item.id !== batch.id)]);
      request.current = null; onStarted(); refresh.current();
    } catch (err) { setError(err instanceof Error ? err.message : "The batch could not be started."); }
    finally { lock.current = false; setBusy(false); }
  }

  const active = batches.find((batch) => batch.id === activeId);
  const finished = active ? active.counts.completed + active.counts.error : 0;
  return <Panel className="mb-3">
    <PanelHeader title="Batch analysis" sub="Select documents in the Vault table, then analyze them together using the settings above." />
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-ink-muted">{selectedIds.length} selected · up to 50 documents per batch. Work continues if you leave this page.</p><button type="button" onClick={start} disabled={busy || !selectedIds.length || selectedIds.length > 50} className="btn btn-primary">{busy ? "Starting batch…" : `Analyze selected (${selectedIds.length})`}</button></div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {loadError && <p role="alert" className="text-sm text-danger">{loadError}</p>}
      {loading && <p role="status" className="text-xs text-ink-muted">Loading batch history…</p>}
      {!loading && !batches.length && <p className="text-xs text-ink-muted">No batches yet. Each document gets its own saved run and reports.</p>}
      {!!batches.length && <label className="block text-xs"><span className="eyebrow mb-1 block">Recent batches</span><select value={activeId ?? ""} onChange={(event) => setActiveId(event.target.value)} className="w-full rounded border border-line bg-surface p-2">{batches.map((batch) => <option key={batch.id} value={batch.id}>{new Date(batch.created_at).toLocaleString()} / {batch.counts.total} documents / {batch.status.replaceAll("_", " ")}</option>)}</select></label>}
      {active && <div>
        <p className="mb-2 text-xs text-ink-muted">Saved settings: {active.request.profile} / {active.request.analysis_mode.replaceAll("_", " ")}</p>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><p role="status" className="text-xs text-ink-muted">{finished}/{active.counts.total} finished · {active.counts.error} failed · {active.counts.pending + active.counts.queued} waiting</p><StatusPill tone={active.status === "completed_with_errors" ? "caution" : active.status === "completed" ? "verified" : "info"} dot={false}>{active.status.replaceAll("_", " ")}</StatusPill></div>
        <progress aria-label="Batch progress" max={active.counts.total} value={finished} className="mb-3 h-2 w-full accent-[#c94f30]" />
        <ul className="max-h-80 divide-y divide-line overflow-auto rounded border border-line">{active.items.map((item) => <li key={item.id} className="p-3 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><span className="min-w-0 break-all font-medium">{item.filename}</span><span className="font-mono text-ink-muted">{item.status}</span></div>{item.error && <p className="mt-1 text-danger">{item.error}</p>}<div className="mt-2 flex flex-wrap gap-4">{item.run_id && <Link className="text-signal hover:underline" href={`/runs/${item.run_id}`}>Open run #{item.run_id}</Link>}{["queued", "running", "completed", "error"].includes(item.status) && <Link className="text-signal hover:underline" href={`/workbench?job=${item.job_id}`}>Inspect progress and results</Link>}</div></li>)}</ul>
      </div>}
    </div>
  </Panel>;
}
