"use client";

import { Panel, PanelHeader, SourceChip } from "@/components/ui";
import { useLive, fetchAuditLogs } from "@/lib/live";
import { ScrollText } from "lucide-react";

const levelStyle: Record<string, { dot: string; text: string }> = {
  info: { dot: "bg-info", text: "text-ink-muted" },
  secure: { dot: "bg-verified", text: "text-verified" },
  warn: { dot: "bg-caution", text: "text-caution" },
  block: { dot: "bg-danger", text: "text-danger" },
};

export function AuditLogPanel() {
  const { data: entries, source } = useLive(fetchAuditLogs, []);
  const rows = entries;

  return (
    <Panel className="flex flex-col">
      <PanelHeader
        title="Audit Log"
        sub="Tamper-evident · local"
        icon={<ScrollText className="h-4 w-4" />}
        right={<SourceChip source={source} />}
      />
      <div className="flex-1 overflow-y-auto p-2">
        <ul className="space-y-0.5">
          {rows.map((a, i) => {
            const st = levelStyle[a.level] ?? levelStyle.info;
            return (
              <li key={i} className="flex items-start gap-2 rounded-[2px] px-2 py-1.5 hover:bg-surface-raised">
                <span className={`led mt-1 ${st.dot}`} />
                <span className="font-mono text-2xs text-ink-faint">{a.ts}</span>
                <div className="min-w-0 flex-1">
                  <span className={`font-mono text-2xs ${st.text}`}>{a.action}</span>
                  <span className="ml-1.5 font-mono text-2xs text-ink-faint">— {a.detail}</span>
                  <div className="font-mono text-2xs text-ink-faint/70">{a.actor}</div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
      {source === "live" && !rows.length && <p className="p-4 text-xs text-ink-muted">No audit entries yet.</p>}
    </Panel>
  );
}
