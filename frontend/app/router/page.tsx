"use client";

import { useState } from "react";
import { Panel, PanelHeader, PageTitle, StatusPill, Meter } from "@/components/ui";
import { models, routingRules, modelById } from "@/lib/data";
import type { ModelKind } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Cpu, Eye, Code2, Zap, Boxes, ArrowRight, Waypoints, Target } from "lucide-react";

const kindIcon: Record<ModelKind, React.ReactNode> = {
  reasoning: <Cpu className="h-4 w-4" />,
  vision: <Eye className="h-4 w-4" />,
  code: <Code2 className="h-4 w-4" />,
  fast: <Zap className="h-4 w-4" />,
  embedding: <Boxes className="h-4 w-4" />,
};

export default function RouterPage() {
  const [activeRule, setActiveRule] = useState(0);
  const rule = routingRules[activeRule];
  const selectedModel = modelById(rule.modelId);

  return (
    <div>
      <PageTitle eyebrow="Adaptive Model Selection" title="Model Router">
        <StatusPill tone="signal" dot={false}>
          <Waypoints className="h-3 w-3" /> {models.length} local models
        </StatusPill>
      </PageTitle>

      {/* headline principle */}
      <Panel className="mb-3">
        <div className="grid items-center gap-4 p-5 md:grid-cols-[1fr_auto]">
          <div>
            <h2 className="font-display text-lg font-semibold text-ink">
              KAVACH does not send every task to one model.
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-muted">
              A lightweight classifier inspects each request and routes it to the local model best suited to
              the work — vision for diagrams, a reasoning model for cross-referencing, a small fast model for
              extraction. Right task → right agent → right model, all on-premise.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-[3px] border border-signal/25 bg-signal/[0.06] px-4 py-3">
            {["Right Task", "Right Agent", "Right Model"].map((t, i) => (
              <div key={t} className="flex items-center gap-2">
                <div className="text-center">
                  <Target className={cn("mx-auto h-4 w-4", i === 2 ? "text-verified" : "text-signal")} />
                  <div className="mt-1 font-mono text-2xs uppercase tracking-wide text-ink">{t}</div>
                </div>
                {i < 2 && <ArrowRight className="h-3.5 w-3.5 text-ink-faint" />}
              </div>
            ))}
          </div>
        </div>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
        {/* Routing flow — interactive */}
        <Panel>
          <PanelHeader title="Live Routing" sub="Pick a task to see the routing decision" />
          <div className="p-4">
            {/* task chips */}
            <div className="mb-4 flex flex-wrap gap-1.5">
              {routingRules.map((r, i) => (
                <button
                  key={r.taskType}
                  onClick={() => setActiveRule(i)}
                  className={cn(
                    "rounded-[2px] border px-2.5 py-1.5 text-left font-mono text-2xs transition-colors",
                    i === activeRule
                      ? "border-signal/50 bg-signal/10 text-signal"
                      : "border-line bg-surface-inset text-ink-muted hover:border-line-strong",
                  )}
                >
                  {r.taskType}
                </button>
              ))}
            </div>

            {/* flow diagram */}
            <div className="flex items-stretch gap-2">
              <FlowNode label="Task" value={rule.taskType} tone="ink" />
              <Arrow />
              <FlowNode label="Classifier" value="llama3.2:3b" tone="info" />
              <Arrow />
              <FlowNode label="Router" value="policy match" tone="signal" />
            </div>

            <div className="my-3 flex justify-center">
              <ArrowRight className="h-4 w-4 rotate-90 text-signal/60" />
            </div>

            {/* selected model card */}
            {selectedModel && (
              <div className="animate-fadein rounded-[3px] border border-signal/40 bg-signal/[0.06] p-4">
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="grid h-8 w-8 place-items-center rounded-[3px] border border-signal/40 bg-signal/10 text-signal">
                      {kindIcon[selectedModel.kind]}
                    </span>
                    <div>
                      <div className="font-display text-sm font-semibold text-ink">{selectedModel.name}</div>
                      <div className="font-mono text-2xs text-ink-muted">{selectedModel.role}</div>
                    </div>
                  </div>
                  <StatusPill tone="verified">Selected</StatusPill>
                </div>
                <div className="rounded-[3px] border border-line bg-surface-inset px-3 py-2">
                  <span className="eyebrow">Reason</span>
                  <p className="mt-0.5 text-xs text-ink">“{rule.reason}”</p>
                </div>
              </div>
            )}
          </div>
        </Panel>

        {/* Available models */}
        <Panel>
          <PanelHeader title="Available Local Models" sub="Loaded on the on-prem GPU" />
          <ul className="divide-y divide-line">
            {models.map((m) => {
              const isSel = m.id === rule.modelId;
              return (
                <li
                  key={m.id}
                  className={cn("px-4 py-3 transition-colors", isSel && "bg-signal/[0.05]")}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        "grid h-8 w-8 place-items-center rounded-[3px] border",
                        isSel ? "border-signal/40 bg-signal/10 text-signal" : "border-line bg-surface-inset text-ink-muted",
                      )}
                    >
                      {kindIcon[m.kind]}
                    </span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-display text-sm font-semibold text-ink">{m.name}</span>
                        <span className="font-mono text-2xs text-ink-faint">{m.params} · {m.quant}</span>
                      </div>
                      <div className="font-mono text-2xs text-ink-muted">{m.role}</div>
                    </div>
                    <StatusPill tone={m.status === "READY" ? "verified" : "muted"} dot={false}>
                      {m.status}
                    </StatusPill>
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-3">
                    <MiniStat label="Model Size" value={`${m.sizeGb} GB`} />
                    <MiniStat label="Context" value={m.ctx} />
                    <MiniStat label="Throughput" value={m.tokensPerSec ? `${m.tokensPerSec} t/s` : "—"} />
                  </div>
                </li>
              );
            })}
          </ul>
        </Panel>
      </div>

      {/* Routing rule table */}
      <Panel className="mt-3">
        <PanelHeader title="Routing Policy" sub="Deterministic task → model mapping" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line font-mono text-2xs uppercase tracking-wider text-ink-faint">
                <th className="px-4 py-2 font-medium">Task Type</th>
                <th className="px-3 py-2 font-medium">Selected Model</th>
                <th className="px-3 py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {routingRules.map((r) => {
                const m = modelById(r.modelId);
                return (
                  <tr key={r.taskType} className="hover:bg-surface-raised">
                    <td className="px-4 py-2.5 text-ink">{r.taskType}</td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1.5 font-mono text-signal">
                        {m && kindIcon[m.kind]} {m?.name}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-2xs text-ink-muted">{r.reason}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function FlowNode({ label, value, tone }: { label: string; value: string; tone: "ink" | "info" | "signal" }) {
  const t = tone === "signal" ? "text-signal" : tone === "info" ? "text-info" : "text-ink";
  return (
    <div className="flex-1 rounded-[3px] border border-line bg-surface-inset px-3 py-2.5 text-center">
      <div className="eyebrow mb-1">{label}</div>
      <div className={cn("truncate font-mono text-2xs", t)}>{value}</div>
    </div>
  );
}
function Arrow() {
  return <div className="flex items-center"><ArrowRight className="h-4 w-4 text-ink-faint" /></div>;
}
function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[2px] border border-line bg-surface-inset px-2 py-1.5">
      <div className="font-mono text-2xs text-ink-faint">{label}</div>
      <div className="font-mono text-2xs text-ink">{value}</div>
    </div>
  );
}
