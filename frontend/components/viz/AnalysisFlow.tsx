"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Circle, Loader2, SkipForward, XCircle } from "lucide-react";
import { Panel, PanelHeader, StatusPill } from "@/components/ui";
import type { AnalysisJob, AnalysisStage } from "@/lib/api";
import { cn } from "@/lib/utils";

const terminal = new Set(["completed", "warning", "skipped"]);

export function AnalysisFlow({ job }: { job: AnalysisJob }) {
  const active = job.stages.find((stage) => stage.status === "running");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const busy = job.status === "queued" || job.status === "running";

  useEffect(() => {
    if (!busy) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [busy]);

  const selected = job.stages.find((stage) => stage.id === selectedId) ?? active
    ?? [...job.stages].reverse().find((stage) => stage.status !== "pending");
  const done = job.stages.filter((stage) => terminal.has(stage.status)).length;
  const elapsed = Math.max(0, Math.floor(((busy ? now : Date.parse(job.updated_at)) - Date.parse(job.created_at)) / 1000));
  const heading = job.status === "queued" ? "Waiting for a local analysis worker"
    : active?.message || (job.status === "error" ? "Analysis stopped" : "Analysis finished");

  return (
    <Panel>
      <PanelHeader title="Live analysis flow" sub={job.document?.filename ?? "Stored document"}
        right={<StatusPill tone={job.status === "error" ? "danger" : busy ? "signal" : "verified"} pulse={busy}>
          {job.status === "completed" ? "Results ready" : job.status}
        </StatusPill>} />
      <div className="space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="status" aria-live="polite" className="min-w-0">
            <p className="text-sm font-semibold text-ink">{heading}</p>
            <p className="mt-1 text-xs text-ink-muted">
              {busy ? "Stages update as the backend performs each operation." : "This flow records the operations performed on your document."}
            </p>
          </div>
          <p className="font-mono text-xs text-ink-muted">{done}/{job.stages.length} stages finished / {elapsed}s elapsed</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {job.stages.map((stage, index) => {
            const Icon = stage.status === "running" ? Loader2
              : stage.status === "completed" ? CheckCircle2
                : stage.status === "warning" ? AlertTriangle
                  : stage.status === "error" ? XCircle
                    : stage.status === "skipped" || stage.status === "not_run" ? SkipForward : Circle;
            return <button key={stage.id} onClick={() => setSelectedId(stage.id)}
              aria-pressed={selected?.id === stage.id}
              className={cn("flex items-start gap-3 rounded border p-3 text-left transition-colors",
                selected?.id === stage.id ? "border-signal bg-signal/5" : "border-line bg-surface-inset",
                stage.status === "running" && "ring-1 ring-signal/20")}>
              <Icon className={cn("mt-0.5 h-4 w-4 shrink-0",
                stage.status === "running" ? "animate-spin text-signal motion-reduce:animate-none"
                  : stage.status === "completed" ? "text-verified"
                    : stage.status === "error" ? "text-danger"
                      : stage.status === "warning" ? "text-caution" : "text-ink-faint")} />
              <span className="min-w-0 flex-1">
                <span className="block text-xs font-semibold text-ink">{index + 1}. {stage.label}</span>
                <span className="mt-1 block font-mono text-2xs capitalize text-ink-muted">{stage.status.replaceAll("_", " ")}</span>
              </span>
            </button>;
          })}
        </div>
        {selected && <StageDetails stage={selected} now={now} />}
        {job.error && <p role="alert" className="rounded border border-danger/30 bg-danger/5 p-3 text-sm text-danger">{job.error}</p>}
      </div>
    </Panel>
  );
}

function StageDetails({ stage, now }: { stage: AnalysisStage; now: number }) {
  const seconds = stage.started_at ? Math.max(0, Math.floor(((stage.finished_at ? Date.parse(stage.finished_at) : now) - Date.parse(stage.started_at)) / 1000)) : null;
  const model = typeof stage.metadata.model === "string" ? stage.metadata.model : null;
  return <div className="rounded border border-line bg-surface-inset p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm font-semibold">{stage.label}</p>
      {seconds !== null && <span className="font-mono text-2xs text-ink-faint">{seconds}s in this stage</span>}
    </div>
    <p className="mt-1 text-xs text-ink-muted">{stage.description}</p>
    {stage.message && <p className="mt-3 text-sm text-ink">{stage.message}</p>}
    {stage.detail && <p className="mt-1 whitespace-pre-wrap break-words text-xs text-ink-muted">{stage.detail}</p>}
    {model && <p className="mt-2 font-mono text-2xs text-signal">Local model: {model}</p>}
    {stage.events.length > 0 && <details className="mt-3 border-t border-line pt-2">
      <summary className="cursor-pointer text-xs text-ink-muted">View stage activity ({stage.events.length})</summary>
      <ol className="mt-2 space-y-2">
        {stage.events.map((event, index) => <li key={`${event.at}-${index}`} className="border-l-2 border-line pl-3">
          <p className="text-xs text-ink"><span className="mr-2 font-mono text-2xs text-ink-faint">{new Date(event.at).toLocaleTimeString()}</span>{event.message}</p>
          {event.detail && <p className="mt-0.5 whitespace-pre-wrap break-words text-2xs text-ink-muted">{event.detail}</p>}
        </li>)}
      </ol>
    </details>}
  </div>;
}
