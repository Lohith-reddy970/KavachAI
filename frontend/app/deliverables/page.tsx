"use client";
import { Panel, PanelHeader, PageTitle, SourceChip } from "@/components/ui";
import { useLive, fetchDeliverables } from "@/lib/live";
export default function DeliverablesPage() {
  const { data: items, source, error } = useLive(fetchDeliverables, []);
  return <div><PageTitle eyebrow="Generated outputs" title="Deliverables"><SourceChip source={source} /></PageTitle>
    {error && <p role="alert" className="mb-3 text-danger">Could not load reports: {error}</p>}
    {source === "live" && !items.length && <p className="text-ink-muted">No reports generated yet. Analyze a document to create one.</p>}
    <div className="grid gap-3 md:grid-cols-2">{items.map((item) => <Panel key={item.id}>
      <PanelHeader title={item.title} sub={`${item.format} / ${item.sizeKb} KB / ${item.createdAt}`} />
      <div className="space-y-3 p-4"><p className="text-sm text-ink-muted">{item.project}. Open Agent Runs for evidence and review decisions.</p><a href={item.downloadUrl} className="btn btn-primary">Download {item.format}</a></div>
    </Panel>)}</div>
  </div>;
}
