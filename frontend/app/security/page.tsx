"use client";
import { Panel, PanelHeader, PageTitle, SourceChip } from "@/components/ui";
import { AuditLogPanel } from "@/components/viz/AuditLogPanel";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
export default function SecurityPage() {
  const { data, source } = useLive(api.systemStatus, null);
  return <div><PageTitle eyebrow="Local processing policy" title="Security Center"><SourceChip source={source} /></PageTitle>
    <Panel className="mb-3"><PanelHeader title="Configured controls" /><div className="space-y-2 p-4 text-sm"><p>Mode: {data?.mode ?? "unavailable"}</p><p>Provider policy: {data?.network ?? "unavailable"}</p><p>Code execution: {data?.sandbox?.status ?? "unavailable"}</p><p className="text-ink-muted">Application restrictions limit model connections. Configure host firewalls, access control, and disk encryption for your deployment. Audit records are stored in local SQLite.</p></div></Panel><AuditLogPanel />
  </div>;
}
