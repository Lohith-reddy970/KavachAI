"use client";
import type { Evidence } from "@/lib/types";
import { Tag, Meter } from "@/components/ui";
import { FileText } from "lucide-react";

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
