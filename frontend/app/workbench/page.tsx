"use client";

import { useEffect, useState } from "react";
import {
  Panel,
  PanelHeader,
  PageTitle,
  StatusPill,
} from "@/components/ui";
import { ExecutionTimeline } from "@/components/viz/ExecutionTimeline";
import { FindingCard } from "@/components/viz/Findings";
import { ReportView } from "@/components/viz/ReportView";
import { PidViewer } from "@/components/viz/PidViewer";
import { useKavach } from "@/lib/store";
import { documents, findings, SAMPLE_TASK } from "@/lib/data";
import { useLive, fetchAnalysisCatalog, fetchDocuments } from "@/lib/live";
import { api, type AgentRunResponse, type AnalysisMode } from "@/lib/api";
import Link from "next/link";
import type { KDocument } from "@/lib/types";
import { sampleAnalysisCatalog } from "@/lib/profiles";
import {
  RotateCcw,
  FileText,
  Terminal,
  FileOutput,
  Workflow,
  Lock,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function WorkbenchPage() {
  const [task, setTask] = useState(SAMPLE_TASK);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [analysisState, setAnalysisState] = useState<
    "idle" | "running" | "done" | "error"
  >("idle");
  const [analysisMessage, setAnalysisMessage] = useState<string | null>(null);
  const [profile, setProfile] = useState("general");
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("risk_review");
  const { data: availableDocuments, source: documentSource } = useLive(
    fetchDocuments,
    documents,
  );
  const { data: analysisCatalog } = useLive(
    fetchAnalysisCatalog,
    sampleAnalysisCatalog,
  );
  const [agentState, setAgentState] = useState<"idle" | "running" | "error">(
    "idle",
  );
  const [agentRun, setAgentRun] = useState<AgentRunResponse | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [tab, setTab] = useState<"pipeline" | "pid">("pipeline");
  const phase = useKavach((s) => s.phase);
  const startRun = useKavach((s) => s.startRun);
  const reset = useKavach((s) => s.reset);
  const progress = useKavach((s) => s.progress);
  const logLines = useKavach((s) => s.logLines);
  const showReport = useKavach((s) => s.showReport);
  const openReport = useKavach((s) => s.openReport);
  const closeReport = useKavach((s) => s.closeReport);

  const started = phase !== "idle";
  const finished = phase === "review" || phase === "complete";
  const selectedDocument = availableDocuments.find(
    (document) => document.id === selectedDocumentId,
  );
  const canAnalyzeSelectedDocument =
    documentSource === "live" && !!selectedDocument && /^\d+$/.test(selectedDocument.id);
  const needsReview = findings.filter(
    (f) => !f.verified || f.reviewState === "needs-review",
  );

  useEffect(() => {
    if (
      availableDocuments.length > 0 &&
      !availableDocuments.some((document) => document.id === selectedDocumentId)
    ) {
      const textDocument = availableDocuments.find((document) =>
        ["PDF", "DOCX", "TXT", "CSV", "PY"].includes(document.type),
      );
      setSelectedDocumentId((textDocument ?? availableDocuments[0]).id);
    }
  }, [availableDocuments, selectedDocumentId]);

  async function analyzeSelectedDocument() {
    if (!canAnalyzeSelectedDocument || !selectedDocument) {
      setAnalysisState("error");
      setAnalysisMessage("Select a document loaded from the backend before analysis.");
      return;
    }
    setAnalysisState("running");
    setAnalysisMessage(null);
    try {
      const documentName = selectedDocument.name;
      const title = analysisMode === "risk_review"
        ? task || `Review ${documentName}`
        : analysisMode === "summary"
          ? `Summarize ${documentName}`
          : `Extract fields from ${documentName}`;
      const description = analysisMode === "risk_review"
        ? "Review this document for risks and support each finding with source evidence."
        : analysisMode === "summary"
          ? "Summarize the document's purpose, key points, decisions, and open questions."
          : "Extract dates, equipment identifiers, and measurements with exact source excerpts.";
      const result = await api.analyzeDocument(
        selectedDocumentId,
        title,
        description,
        profile,
        analysisMode,
      );
      setAnalysisState("done");
      const outcome = analysisMode === "summary"
        ? "summary generated"
        : analysisMode === "extract_fields"
          ? `${result.run.findings.length} field(s) extracted`
          : `${result.run.findings.length} risk finding(s) recorded`;
      setAnalysisMessage(`Run #${result.run.run.id}: ${outcome}. Open Agent Runs to view the result.`);
    } catch (error) {
      setAnalysisState("error");
      setAnalysisMessage(
        error instanceof Error ? error.message : "Document analysis failed",
      );
    }
  }

  async function runPlanner() {
    if (!task.trim() || documentSource !== "live") return;
    setAgentState("running");
    setAgentError(null);
    try {
      setAgentRun(await api.agentRun(task.trim().slice(0, 2000)));
      setAgentState("idle");
    } catch (error) {
      setAgentRun(null);
      setAgentState("error");
      setAgentError(
        error instanceof Error ? error.message : "Agentic run failed",
      );
    }
  }

  return (
    <div>
      <PageTitle eyebrow="Agentic Workspace" title="Workbench">
        <StatusPill
          tone={
            finished ? "verified" : phase === "running" ? "signal" : "muted"
          }
          pulse={phase === "running"}
        >
          {phase === "idle"
            ? "Ready"
            : phase === "running"
              ? `Executing · ${progress}%`
              : "Awaiting Review"}
        </StatusPill>
      </PageTitle>

      <div className="space-y-4">
        {/* Tab bar */}
        <div className="flex items-center gap-1 border-b border-line">
            {(
              [
                ["pipeline", "Agent Pipeline"],
                ["pid", "P&ID Analysis"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={cn(
                  "-mb-px border-b-2 px-3 py-2 font-mono text-2xs uppercase tracking-[0.08em] transition-colors",
                  tab === key
                    ? "border-signal text-signal"
                    : "border-transparent text-ink-muted hover:text-ink",
                )}
              >
                {label}
              </button>
            ))}
        </div>

          {tab === "pid" ? (
            <>
              <Panel>
                <PanelHeader
                  title="Multimodal P&ID Analysis"
                  sub="Vision model · region detection linked to corpus evidence"
                  icon={<FileText className="h-4 w-4" />}
                />
                <div className="p-4">
                  <PidViewer />
                </div>
              </Panel>
            </>
          ) : (
            <>
              {!started ? (
                <Panel>
                  <PanelHeader
                    title="Document analysis"
                    sub="Choose a source, profile, and task"
                    icon={<FileText className="h-4 w-4" />}
                    right={
                      <Link href="/vault" className="font-mono text-2xs text-signal hover:underline">
                        open document vault →
                      </Link>
                    }
                  />
                  <div className="space-y-4 p-4 sm:p-5">
                    <label className="block">
                      <span className="eyebrow mb-1.5 block">Analysis request</span>
                      <textarea
                        value={task}
                        onChange={(e) => setTask(e.target.value)}
                        rows={2}
                        className="w-full resize-y rounded-[3px] border border-line bg-surface-inset px-3 py-2.5 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-signal/50"
                        placeholder="Review the selected document and cite relevant passages."
                      />
                    </label>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="block">
                        <span className="eyebrow mb-1.5 block">Profile</span>
                        <select
                          value={profile}
                          onChange={(e) => setProfile(e.target.value)}
                          className="w-full rounded-[3px] border border-line bg-surface-inset px-3 py-2.5 text-sm text-ink outline-none focus:border-signal/50"
                        >
                          {analysisCatalog.profiles.map((item) => (
                            <option key={item.id} value={item.id}>{item.name}</option>
                          ))}
                        </select>
                      </label>
                      <label className="block">
                        <span className="eyebrow mb-1.5 block">Task</span>
                        <select
                          value={analysisMode}
                          onChange={(e) => setAnalysisMode(e.target.value as AnalysisMode)}
                          className="w-full rounded-[3px] border border-line bg-surface-inset px-3 py-2.5 text-sm text-ink outline-none focus:border-signal/50"
                        >
                          {analysisCatalog.analysis_modes.map((item) => (
                            <option key={item.id} value={item.id}>{item.name}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <p className="-mt-2 text-xs text-ink-muted">
                      These settings apply to document analysis. The agentic planner runs its own sample workflow.
                    </p>

                    <div className="grid gap-3 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                      <label className="block min-w-0">
                        <span className="eyebrow mb-1.5 block">
                          Source document <span className="text-ink-faint">/ {availableDocuments.length} available</span>
                        </span>
                        <select
                          value={selectedDocumentId}
                          onChange={(e) => setSelectedDocumentId(e.target.value)}
                          className="w-full rounded-[3px] border border-line bg-surface-inset px-3 py-2.5 text-sm text-ink outline-none focus:border-signal/50"
                        >
                          {availableDocuments.map((d) => (
                            <option key={d.id} value={d.id}>{d.name}</option>
                          ))}
                        </select>
                      </label>
                      <button
                        onClick={analyzeSelectedDocument}
                        disabled={analysisState === "running" || !canAnalyzeSelectedDocument}
                        className="btn btn-primary min-h-10 whitespace-nowrap"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        {analysisState === "running" ? "Analyzing…" : "Analyze document"}
                      </button>
                    </div>

                    {analysisState === "running" && (
                      <p aria-live="polite" className="font-mono text-2xs text-ink-muted">
                        Local model starting if needed. Keep this page open; first analysis can take a minute.
                      </p>
                    )}

                  <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
                      <span className="flex items-center gap-1.5 font-mono text-2xs text-ink-muted">
                        <Lock className="h-3.5 w-3.5 text-verified" /> Local processing · source citations retained
                      </span>
                      <button
                        onClick={runPlanner}
                        disabled={agentState === "running" || documentSource !== "live" || !task.trim()}
                        className="btn btn-ghost"
                      >
                        <Workflow className="h-3.5 w-3.5" />
                        {agentState === "running" ? "Planning…" : "Run agentic planner"}
                      </button>
                    </div>

                    {analysisMessage && (
                      <p className={cn(
                        "rounded-[3px] border px-3 py-2 font-mono text-2xs",
                        analysisState === "error"
                          ? "border-danger/30 bg-danger/5 text-danger"
                          : "border-verified/30 bg-verified/5 text-verified",
                      )}>
                        {analysisMessage}
                      </p>
                    )}
                    {documentSource !== "live" && (
                      <p className="font-mono text-2xs text-ink-faint">
                        Backend offline — live analysis is unavailable. The sample workflow remains available from the top bar.
                      </p>
                    )}
                  </div>
                </Panel>
              ) : (
                <Panel className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5">
                  <div>
                    <p className="eyebrow mb-1">Sample workflow / {phase === "running" ? "in progress" : "complete"}</p>
                    <p className="font-display text-xl font-semibold uppercase tracking-wide text-ink">
                      {phase === "running" ? "Processing local sample" : "Sample run ready for review"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs text-ink-muted">{progress}%</span>
                    <button onClick={reset} className="btn btn-ghost">
                      <RotateCcw className="h-3.5 w-3.5" /> Reset
                    </button>
                  </div>
                </Panel>
              )}

              {agentError && (
                <p className="rounded-[3px] border border-danger/30 bg-danger/5 px-3 py-2 font-mono text-2xs text-danger">
                  Agentic run failed: {agentError}
                </p>
              )}
              {agentRun && <PlannerTrace run={agentRun} />}

              {started && (
                <>
                  <Panel>
                    <PanelHeader
                      title="Run trace"
                      sub="Select a step to inspect its source and result"
                      right={
                        <span className="font-mono text-2xs text-ink-faint">
                          {progress}% · {phase === "running" ? "running" : "complete"}
                        </span>
                      }
                    />
                    <div className="p-4">
                      <ExecutionTimeline />
                    </div>
                  </Panel>

                  <details className="panel overflow-hidden">
                    <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                      <span className="flex items-center gap-2 font-display text-base font-semibold uppercase tracking-wide text-ink">
                        <Terminal className="h-4 w-4 text-signal" /> Run log
                      </span>
                      <span className="font-mono text-2xs uppercase tracking-wider text-ink-faint">
                        expand
                      </span>
                    </summary>
                    <div className="border-t border-line bg-surface-inset p-4">
                      <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-mono text-2xs leading-relaxed text-ink-muted">
                        {logLines.join("\n")}
                        {phase === "running" && (
                          <span className="animate-blip text-signal">▊</span>
                        )}
                      </pre>
                    </div>
                  </details>

                  {/* Verification + findings */}
                  {finished && (
                    <>
                      <Panel className="animate-fadein">
                        <PanelHeader
                          title="Verification"
                          sub="Evidence cross-check by the Verification Agent"
                          right={
                            <StatusPill tone="verified">
                              Verified 94%
                            </StatusPill>
                          }
                        />
                        <div className="grid gap-3 p-4 sm:grid-cols-4">
                          <VStat
                            label="Verification Score"
                            value="94%"
                            tone="text-verified"
                          />
                          <VStat
                            label="Evidence-Backed"
                            value="8 / 9"
                            tone="text-signal"
                          />
                          <VStat
                            label="Needs Human Review"
                            value="1"
                            tone="text-caution"
                          />
                          <div className="flex items-center">
                            <button
                              onClick={openReport}
                              className="btn btn-primary w-full shadow-glow"
                            >
                              <FileOutput className="h-3.5 w-3.5" /> Open
                              Engineering Review
                            </button>
                          </div>
                        </div>
                      </Panel>

                      <Panel className="animate-fadein">
                        <PanelHeader
                          title="Human Review Required"
                          sub="AI recommends · Reviewer decides"
                          right={
                            <StatusPill tone="caution" dot={false}>
                              {needsReview.length} pending
                            </StatusPill>
                          }
                        />
                        <div className="space-y-2.5 p-4">
                          {needsReview.map((f) => (
                            <FindingCard key={f.id} finding={f} showReview />
                          ))}
                        </div>
                      </Panel>
                    </>
                  )}
                </>
              )}
            </>
          )}
      </div>

      {/* Report modal */}
      {showReport && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/80 p-4 backdrop-blur-sm"
          onClick={closeReport}
        >
          <div
            className="panel-raised h-[88vh] w-full max-w-4xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <ReportView onClose={closeReport} />
          </div>
        </div>
      )}
    </div>
  );
}

function VStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className="rounded-[3px] border border-line bg-surface-inset p-3">
      <div className="eyebrow mb-1">{label}</div>
      <div className={cn("font-display text-2xl font-bold", tone)}>{value}</div>
    </div>
  );
}

/** The planner's own decisions for a bounded agentic run on the backend. */
function PlannerTrace({ run }: { run: AgentRunResponse }) {
  const plan = run.planner;
  const status = run.run.status;
  return (
    <Panel className="animate-fadein">
      <PanelHeader
        title={`Agentic Planner · Run #${run.run.id}`}
        sub={`${plan.steps_used} of ${plan.max_steps} steps · stop: ${plan.stop_reason.replace(/_/g, " ")} · provider ${plan.provider}`}
        icon={<Workflow className="h-4 w-4" />}
        right={
          <StatusPill
            tone={
              status === "completed"
                ? "verified"
                : status === "awaiting_review"
                  ? "caution"
                  : "danger"
            }
            dot={false}
          >
            {status.replace("_", " ")}
          </StatusPill>
        }
      />
      <ol className="divide-y divide-line">
        {plan.trace.map((t) => (
          <li key={t.step} className="flex gap-3 px-4 py-2">
            <span className="font-mono text-2xs text-signal">
              {String(t.step).padStart(2, "0")}
            </span>
            <div className="flex-1">
              <span className="font-mono text-xs text-ink">{t.action}</span>
              <p className="text-2xs text-ink-muted">{t.reason}</p>
            </div>
            <span
              className={cn(
                "font-mono text-2xs",
                t.status === "completed" ? "text-verified" : "text-danger",
              )}
            >
              {t.status}
            </span>
          </li>
        ))}
      </ol>
      <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-2.5 font-mono text-2xs text-ink-muted">
        <span>
          {run.findings.length} finding(s) ·{" "}
          {run.findings.filter((f) => f.needs_review).length} held for human
          review
        </span>
        <Link href="/runs" className="text-signal hover:underline">
          Review in Agent Runs →
        </Link>
      </div>
    </Panel>
  );
}
