"use client";

import { findings, FACILITY, UNIT } from "@/lib/data";
import { buildReportText, downloadText } from "@/lib/report";
import { FindingCard } from "@/components/viz/Findings";
import { StatusPill, Meter } from "@/components/ui";
import { Download, ShieldCheck, FileText, X } from "lucide-react";
import { useKavach } from "@/lib/store";

export function ReportView({ onClose }: { onClose?: () => void }) {
  const setReview = useKavach((s) => s.setReview);
  const reviews = useKavach((s) => s.reviews);
  const approvedCount = findings.filter((f) => (reviews[f.id] ?? f.reviewState) === "approved").length;

  return (
    <div className="flex h-full flex-col">
      {/* letterhead */}
      <div className="flex items-start justify-between border-b border-line px-6 py-4">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-[3px] border border-signal/40 bg-signal/10 text-signal">
            <FileText className="h-5 w-5" />
          </span>
          <div>
            <div className="eyebrow mb-1">Engineering Review Report · CONFIDENTIAL</div>
            <h2 className="font-display text-lg font-bold text-ink">Unit 4 Inspection — Engineering Review</h2>
            <p className="font-mono text-2xs text-ink-muted">
              {FACILITY} · {UNIT} · generated on-premise · RUN-2026-0912
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => downloadText("KAVACH_Engineering_Review_Unit4.txt", buildReportText())}
            className="btn btn-primary"
          >
            <Download className="h-3.5 w-3.5" /> Download
          </button>
          {onClose && (
            <button onClick={onClose} className="btn btn-ghost px-2">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {/* summary bar */}
        <div className="mb-5 grid gap-3 sm:grid-cols-4">
          <SummaryStat label="Verification" value="94%" tone="verified" bar={94} />
          <SummaryStat label="Evidence-Backed" value="8 / 9" tone="signal" bar={89} />
          <SummaryStat label="Needs Review" value="1" tone="caution" bar={11} />
          <SummaryStat label="Reviewer-Approved" value={`${approvedCount} / ${findings.length}`} tone="verified" bar={(approvedCount / findings.length) * 100} />
        </div>

        <section className="mb-5">
          <h3 className="eyebrow mb-2">Executive Summary</h3>
          <p className="text-sm leading-relaxed text-ink-muted">
            Cross-analysis of the Unit 4 inspection report against the plant P&ID and engineering
            documentation identified <span className="text-ink">9 findings</span> across{" "}
            <span className="text-ink">6 equipment items</span>. One high-severity item
            (<span className="text-danger">P-101 outlet wall thickness</span>) and one unverified hypothesis
            require reviewer attention before approval. Overall verification score is{" "}
            <span className="text-verified">94%</span>, with 8 of 9 findings backed by retrieved source evidence.
          </p>
        </section>

        <section>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="eyebrow">Findings & Evidence</h3>
            <StatusPill tone="caution" dot={false}>
              <ShieldCheck className="h-3 w-3" /> Human sign-off required
            </StatusPill>
          </div>
          <div className="space-y-2.5">
            {findings.map((f) => (
              <FindingCard key={f.id} finding={f} showReview />
            ))}
          </div>
        </section>
      </div>

      <div className="flex items-center justify-between border-t border-line bg-surface-inset px-6 py-3">
        <span className="font-mono text-2xs text-ink-faint">
          AI recommends · Reviewer decides — not authoritative until signed off
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => findings.forEach((f) => setReview(f.id, "approved"))}
            className="btn btn-primary"
          >
            <ShieldCheck className="h-3.5 w-3.5" /> Approve All & Sign Off
          </button>
        </div>
      </div>
    </div>
  );
}

function SummaryStat({
  label,
  value,
  tone,
  bar,
}: {
  label: string;
  value: string;
  tone: "verified" | "signal" | "caution";
  bar: number;
}) {
  const t = tone === "verified" ? "text-verified" : tone === "caution" ? "text-caution" : "text-signal";
  return (
    <div className="rounded-[3px] border border-line bg-surface p-3">
      <div className="eyebrow mb-1.5">{label}</div>
      <div className={`mb-2 font-display text-2xl font-bold ${t}`}>{value}</div>
      <Meter value={bar} tone={tone} />
    </div>
  );
}
