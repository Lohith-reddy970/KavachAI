"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { api, type LiveRun, type LiveRunDetail } from "@/lib/api";
import { Panel, PanelHeader, StatusPill } from "@/components/ui";
import { Activity, Check, ChevronDown, ChevronRight, Download, X } from "lucide-react";

type Tone = "verified" | "signal" | "caution" | "danger" | "info" | "muted";

const runTone: Record<string, Tone> = {
  completed: "verified",
  running: "signal",
  awaiting_review: "caution",
  halted: "danger",
  error: "danger",
};
const stepTone: Record<string, string> = {
  completed: "text-verified",
  awaiting_review: "text-caution",
  warning: "text-caution",
  skipped: "text-ink-faint",
  halted: "text-danger",
  error: "text-danger",
};
const sevTone: Record<string, Tone> = {
  critical: "danger",
  high: "danger",
  medium: "caution",
  low: "signal",
  info: "info",
};

function kind(scenario: string | null): string {
  if (scenario === "agentic") return "Agentic planner";
  if (scenario?.startsWith("document:")) return `Document · ${scenario.slice(9)}`;
  return "Sample scenario pipeline";
}

/**
 * Runs recorded by the FastAPI backend (sample pipeline, uploaded-document
 * analysis and agentic planner runs). Renders nothing while the backend is
 * offline, so the page falls back to the baked run history below it.
 */
export function LiveRuns() {
  const [runs, setRuns] = useState<LiveRun[] | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<LiveRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRuns(await api.runs());
    } catch {
      setRuns(null); // backend offline
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function open(id: number) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    setDetail(null);
    setError(null);
    try {
      setDetail(await api.run(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load run");
    }
  }

  async function review(findingId: number, decision: "approve" | "reject") {
    if (openId === null) return;
    setError(null);
    try {
      await api.reviewFinding(findingId, decision);
      setDetail(await api.run(openId));
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    }
  }

  if (!runs) return null;

  return (
    <Panel className="mb-3">
      <PanelHeader
        title="Backend Runs"
        icon={<Activity className="h-4 w-4" />}
        sub="Recorded by the local FastAPI backend · select a run for its trace, findings and approvals"
        right={
          <StatusPill tone="verified" pulse>
            Live Backend
          </StatusPill>
        }
      />
      {runs.length === 0 ? (
        <p className="px-4 py-6 text-xs text-ink-muted">
          No runs yet. Start one from the Workbench or analyze a document in the Vault.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line font-mono text-2xs uppercase tracking-wider text-ink-faint">
                <th className="w-8 px-2 py-2"></th>
                <th className="px-2 py-2 font-medium">Run</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Started</th>
                <th className="px-3 py-2 font-medium">Verify</th>
                <th className="px-3 py-2 font-medium">Evidence</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {runs.map((r) => (
                <Fragment key={r.id}>
                  <tr
                    onClick={() => open(r.id)}
                    className="cursor-pointer hover:bg-surface-raised"
                  >
                    <td className="px-2 py-3 text-ink-faint">
                      {openId === r.id ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </td>
                    <td className="px-2 py-3 font-mono text-signal">#{r.id}</td>
                    <td className="max-w-[260px] truncate px-3 py-3 text-ink">{kind(r.scenario)}</td>
                    <td className="px-3 py-3 font-mono text-2xs text-ink-faint">
                      {(r.started_at ?? "").replace("T", " ").slice(0, 19)}
                    </td>
                    <td className="px-3 py-3 font-mono text-ink">
                      {r.verification_score === null ? "n/a" : `${r.verification_score}%`}
                    </td>
                    <td className="px-3 py-3 font-mono text-ink-muted">{r.evidence_backed || "—"}</td>
                    <td className="px-3 py-3">
                      <StatusPill tone={runTone[r.status] ?? "muted"} dot={false}>
                        {r.status.replace("_", " ")}
                      </StatusPill>
                    </td>
                  </tr>
                  {openId === r.id && (
                    <tr>
                      <td colSpan={7} className="bg-surface-inset px-4 py-4">
                        {error && <p className="mb-2 font-mono text-2xs text-danger">{error}</p>}
                        {!detail && !error && (
                          <p className="font-mono text-2xs text-ink-muted">Loading run…</p>
                        )}
                        {detail && <RunDetail detail={detail} onReview={review} />}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function RunDetail({
  detail,
  onReview,
}: {
  detail: LiveRunDetail;
  onReview: (findingId: number, decision: "approve" | "reject") => void;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div>
        <p className="eyebrow mb-2">Execution trace · {detail.steps.length} steps</p>
        <ol className="space-y-1.5">
          {detail.steps.map((s) => (
            <li key={s.id} className="rounded-[3px] border border-line bg-surface px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-2xs uppercase tracking-wider text-signal">
                  {s.agent.replace(/_/g, " ")}
                </span>
                <span className={`font-mono text-2xs ${stepTone[s.status] ?? "text-ink-faint"}`}>
                  {s.status.replace("_", " ")}
                </span>
              </div>
              <p className="text-xs text-ink">{s.message}</p>
              {s.detail && <p className="font-mono text-2xs text-ink-muted">{s.detail}</p>}
            </li>
          ))}
        </ol>
      </div>

      <div>
        <p className="eyebrow mb-2">Findings · {detail.findings.length}</p>
        {detail.findings.length === 0 && (
          <p className="text-xs text-ink-muted">This run produced no findings.</p>
        )}
        <div className="space-y-2">
          {detail.findings.map((f) => (
            <div
              key={f.id}
              className={`rounded-[3px] border bg-surface p-3 ${
                f.needs_review && f.review_status === "pending" ? "border-caution/40" : "border-line"
              }`}
            >
              <div className="mb-1 flex items-start justify-between gap-2">
                <h4 className="text-xs font-semibold leading-snug text-ink">{f.title}</h4>
                <StatusPill tone={sevTone[f.severity] ?? "muted"} dot={false}>
                  {f.severity}
                </StatusPill>
              </div>
              <p className="mb-2 font-mono text-2xs text-ink-faint">
                {f.equipment_id ? `${f.equipment_id} · ` : ""}confidence {f.confidence}%
              </p>
              {f.evidence.map((ev) => (
                <p
                  key={ev.id}
                  className="mb-1.5 border-l-2 border-signal/40 pl-2 text-2xs leading-relaxed text-ink-muted"
                >
                  “{ev.excerpt}”
                  <span className="ml-1 font-mono text-ink-faint">
                    — {ev.source}
                    {ev.page ? ` p.${ev.page}` : ""}
                  </span>
                </p>
              ))}
              {f.needs_review ? (
                <div className="mt-2 flex items-center justify-between gap-2 border-t border-line pt-2">
                  {f.review_status === "approved" ? (
                    <span className="font-mono text-2xs text-verified">✓ Approved by reviewer</span>
                  ) : f.review_status === "rejected" ? (
                    <span className="font-mono text-2xs text-danger">✕ Rejected by reviewer</span>
                  ) : (
                    <>
                      <span className="font-mono text-2xs text-caution">⚠ Held for human review</span>
                      <span className="flex items-center gap-1.5">
                        <button
                          onClick={() => onReview(f.id, "approve")}
                          className="btn btn-ghost px-2 py-1 text-verified hover:border-verified/50"
                        >
                          <Check className="h-3 w-3" /> Approve
                        </button>
                        <button
                          onClick={() => onReview(f.id, "reject")}
                          className="btn btn-ghost px-2 py-1 text-danger hover:border-danger/50"
                        >
                          <X className="h-3 w-3" /> Reject
                        </button>
                      </span>
                    </>
                  )}
                </div>
              ) : null}
            </div>
          ))}
        </div>

        {detail.deliverables.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {detail.deliverables.map((d) => (
              <a
                key={d.id}
                href={`${api.base}/api/deliverables/${d.id}/download`}
                className="btn btn-ghost px-2 py-1"
              >
                <Download className="h-3 w-3" /> {(d.fmt ?? "file").toUpperCase()}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
