"use client";
import { Panel, PanelHeader, PageTitle, SourceChip } from "@/components/ui";
import { useLive } from "@/lib/live";
import { api } from "@/lib/api";
export default function RouterPage() {
  const { data, source, error } = useLive(api.models, null);
  return <div><PageTitle eyebrow="Local model assignments" title="Model Router"><SourceChip source={source} /></PageTitle>
    {error && <p role="alert" className="mb-3 text-danger">Model configuration unavailable: {error}</p>}
    {data && <p className="mb-3 text-sm text-ink-muted">Active provider: {data.active_provider}. Configured assignments do not indicate model health or measured performance.</p>}
    <div className="grid gap-3 md:grid-cols-2">{data?.models?.map((model: any) => <Panel key={model.id}><PanelHeader title={model.name} sub={`${model.provider} / ${model.kind}`} /><div className="space-y-2 p-4 text-sm"><p>{model.routing_rule}</p><p className="font-mono text-ink-muted">{model.status}</p></div></Panel>)}</div>
    {data && <Panel className="mt-3"><PanelHeader title="Routing rules" /><ul className="divide-y divide-line">{data.routing_rules.map((rule: any) => <li key={rule.task_type} className="p-4 text-sm"><strong>{rule.task_type}</strong> to {rule.model}<p className="text-xs text-ink-muted">{rule.when}</p></li>)}</ul></Panel>}
  </div>;
}
