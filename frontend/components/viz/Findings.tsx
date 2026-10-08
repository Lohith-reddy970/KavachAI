"use client";

import { getEvidence } from "@/lib/data";
import type { Evidence, Finding } from "@/lib/types";
import { StatusPill, Tag, Meter } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useKavach } from "@/lib/store";
import { FileText, CheckCircle2, AlertTriangle, Check, X, Pencil } from "lucide-react";

export function EvidenceCard({ ev, rank }: { ev: Evidence; rank?: number }) {
  return (
    <div className="rounded-[3px] border border-line bg-surface-inset p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileText className="h-3.5 w-3.5 text-info" />
          <span className="font-mono text-2xs text-ink">{ev.source}</span>
          <span className="font-mono text-2xs text-ink-faint">· p.{ev.page}</span>
        </div>
        {rank ? <span className="font-mono text-2xs text-ink-faint">EV#{rank}</span> : null}
      </div>
      <p className="mb-2 border-l-2 border-signal/40 pl-3 text-xs leading-relaxed text-ink-muted">
        “{ev.excerpt}”
      </p>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5">
          {ev.tags.map((t) => (
            <Tag key={t}>{t}</Tag>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-2xs text-ink-faint">relevance</span>
          <div className="w-16">
            <Meter value={ev.relevance} tone={ev.relevance >= 90 ? "verified" : "signal"} />
          </div>
          <span className="w-8 text-right font-mono text-2xs text-ink">{ev.relevance}%</span>
        </div>
      </div>
    </div>
  );
}

const sevTone: Record<Finding["severity"], "info" | "signal" | "caution" | "danger"> = {
  info: "info",
  low: "signal",
  medium: "caution",
  high: "danger",
};

export function FindingCard({ finding, showReview = false }: { finding: Finding; showReview?: boolean }) {
  const reviews = useKavach((s) => s.reviews);
  const setReview = useKavach((s) => s.setReview);
  const state = reviews[finding.id] ?? finding.reviewState;
  const ev = getEvidence(finding.evidenceIds);

  const confTone = finding.confidence >= 85 ? "verified" : finding.confidence >= 70 ? "caution" : "danger";

  return (
    <div
      className={cn(
        "rounded-[3px] border bg-surface p-4",
        state === "needs-review" ? "border-caution/40" : "border-line",
      )}
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 font-mono text-2xs text-ink-faint">
            #{String(finding.index).padStart(2, "0")}
          </span>
          <div>
            <h4 className="text-sm font-semibold leading-snug text-ink">{finding.title}</h4>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {finding.equipment.map((e) => (
                <Tag key={e}>{e}</Tag>
              ))}
            </div>
          </div>
        </div>
        <StatusPill tone={sevTone[finding.severity]} dot={false}>
          {finding.severity}
        </StatusPill>
      </div>

      <p className="mb-3 text-xs leading-relaxed text-ink-muted">{finding.detail}</p>

      {/* provenance strip */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-[3px] border border-line bg-surface-inset px-3 py-2 sm:grid-cols-4">
        <MetaCol label="Evidence" value={ev.length ? `${ev.length} source${ev.length > 1 ? "s" : ""}` : "none"} tone={ev.length ? "text-ink" : "text-danger"} />
        <MetaCol label="Page" value={ev[0] ? `p.${ev[0].page}` : "—"} tone="text-ink" />
        <div>
          <div className="eyebrow mb-1">Confidence</div>
          <div className="flex items-center gap-2">
            <Meter value={finding.confidence} tone={confTone} className="w-10" />
            <span className="font-mono text-2xs text-ink">{finding.confidence}%</span>
          </div>
        </div>
        <div>
          <div className="eyebrow mb-1">Verification</div>
          {finding.verified ? (
            <span className="inline-flex items-center gap-1 font-mono text-2xs text-verified">
              <CheckCircle2 className="h-3 w-3" /> Supported
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 font-mono text-2xs text-caution">
              <AlertTriangle className="h-3 w-3" /> Unverified
            </span>
          )}
        </div>
      </div>

      {ev.length > 0 && (
        <details className="group mt-2">
          <summary className="cursor-pointer list-none font-mono text-2xs text-signal hover:text-signal-glow">
            ▸ view source evidence
          </summary>
          <div className="mt-2 space-y-2">
            {ev.map((e, i) => (
              <EvidenceCard key={e.id} ev={e} rank={i + 1} />
            ))}
          </div>
        </details>
      )}

      {showReview && (state === "needs-review" || state === "approved" || state === "rejected") && (
        <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-3">
          {state === "approved" ? (
            <span className="font-mono text-2xs text-verified">✓ Approved by reviewer</span>
          ) : state === "rejected" ? (
            <span className="font-mono text-2xs text-danger">✕ Rejected by reviewer</span>
          ) : (
            <span className="font-mono text-2xs text-caution">⚠ Human review required — AI recommends, reviewer decides</span>
          )}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setReview(finding.id, "approved")}
              className="btn btn-ghost px-2 py-1 text-verified hover:border-verified/50"
            >
              <Check className="h-3 w-3" /> Approve
            </button>
            <button className="btn btn-ghost px-2 py-1">
              <Pencil className="h-3 w-3" /> Edit
            </button>
            <button
              onClick={() => setReview(finding.id, "rejected")}
              className="btn btn-ghost px-2 py-1 text-danger hover:border-danger/50"
            >
              <X className="h-3 w-3" /> Reject
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MetaCol({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div>
      <div className="eyebrow mb-1">{label}</div>
      <div className={cn("font-mono text-2xs", tone)}>{value}</div>
    </div>
  );
}
