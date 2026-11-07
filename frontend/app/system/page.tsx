"use client";

import { useEffect, useState } from "react";
import { Panel, PanelHeader, PageTitle, StatusPill, Meter } from "@/components/ui";
import { BackendStatus } from "@/components/viz/BackendStatus";
import { usePolledSystem } from "@/lib/live";
import { Cpu, MemoryStick, Server, Gauge, ShieldCheck } from "lucide-react";

export default function SystemPage() {
  const live = usePolledSystem(5000);
  const [history, setHistory] = useState<number[]>([]);

  useEffect(() => {
    if (live?.gpu != null) setHistory((prev) => [...prev.slice(-39), live.gpu!]);
    else setHistory([]);
  }, [live]);

  const hardware = live?.gpuSource === "hardware";
  const gpu = live?.gpu ?? null;
  const cpu = live?.cpuPct ?? null;
  const ram = live?.ramPct ?? null;
  const gpuName = live?.gpuName ?? "GPU telemetry unavailable";
  const vramUsed = live?.vramUsedGb ?? null;
  const vramTotal = live?.vramTotalGb ?? null;
  const vramLabel =
    vramUsed != null && vramTotal != null
      ? `${vramUsed.toFixed(1)} / ${vramTotal.toFixed(0)} GB`
      : "—";
  const vramPct = vramUsed != null && vramTotal ? (vramUsed / vramTotal) * 100 : 0;
  const spark = history.length >= 2 ? history : [];
  const services = live?.services ?? [];
  const sourcePill = <StatusPill tone={hardware ? "verified" : "muted"}>{hardware ? "Measured GPU" : "GPU unavailable"}</StatusPill>;
  const sourceNote = live ? "Available readings are measured locally. Missing readings are shown as unavailable." : "Backend unavailable. Connect the local service to read system metrics.";

  return (
    <div>
      <PageTitle eyebrow="On-Premise Appliance" title="System">
        <BackendStatus />
      </PageTitle>

      <div className="grid gap-3 lg:grid-cols-3">
        {/* GPU */}
        <Panel className="lg:col-span-2">
          <PanelHeader
            title="Local GPU"
            sub={gpuName}
            icon={<Gauge className="h-4 w-4" />}
            right={
              <span className="flex items-center gap-3">
                {sourcePill}
                <span className="font-mono text-2xs text-signal">
                  {gpu == null ? "unavailable" : `${gpu}% util`}{live?.gpuTempC != null ? ` · ${live.gpuTempC}°C` : ""}
                </span>
              </span>
            }
          />
          <div className="p-4">
            {/* sparkline */}
            <svg viewBox="0 0 200 44" className="mb-4 h-16 w-full" preserveAspectRatio="none">
              <defs>
                <linearGradient id="sp" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#c94f30" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#c94f30" stopOpacity="0" />
                </linearGradient>
              </defs>
              <polyline
                points={spark.map((v, i) => `${(i / (spark.length - 1)) * 200},${44 - (v / 100) * 44}`).join(" ")}
                fill="none"
                stroke="#c94f30"
                strokeWidth="1.5"
              />
              <polygon
                points={`0,44 ${spark.map((v, i) => `${(i / (spark.length - 1)) * 200},${44 - (v / 100) * 44}`).join(" ")} 200,44`}
                fill="url(#sp)"
              />
            </svg>
            <div className="grid grid-cols-3 gap-4">
              <Gauge2 label="GPU Utilisation" value={gpu} unit="%" icon={<Gauge className="h-4 w-4" />} />
              <Gauge2 label="CPU" value={cpu} unit="%" icon={<Cpu className="h-4 w-4" />} />
              <Gauge2 label="System RAM" value={ram} unit="%" icon={<MemoryStick className="h-4 w-4" />} />
            </div>
            <div className="mt-4 rounded-[3px] border border-line bg-surface-inset px-3 py-2">
              <div className="mb-1 flex items-center justify-between font-mono text-2xs text-ink-muted">
                <span>VRAM (model weights + KV cache)</span>
                <span className="text-ink">{vramLabel}</span>
              </div>
              <Meter value={vramPct} />
            </div>
            <p className="mt-3 font-mono text-2xs text-ink-faint">{sourceNote}</p>
          </div>
        </Panel>

        {/* services */}
        <Panel>
          <PanelHeader
            title="Services"
            icon={<Server className="h-4 w-4" />}
            right={sourcePill}
          />
          <ul className="divide-y divide-line">
            {services.map((s) => {
              const unavailable = ["UNAVAILABLE", "OFFLINE", "ERROR", "DISABLED", "UNCONFIGURED"].includes(s.status);
              const tone = unavailable ? "danger"
                : s.status === "AIR-GAPPED" ? "caution"
                  : s.status === "SECURE" ? "info" : "verified";
              return (
                <li key={s.name} className="flex items-center gap-3 px-4 py-2.5">
                  <span className={`led animate-blip ${unavailable ? "bg-danger" : tone === "caution" ? "bg-caution" : tone === "info" ? "bg-info" : "bg-verified"}`} />
                  <div className="flex-1">
                    <div className="font-mono text-xs text-ink">{s.name}</div>
                    <div className="font-mono text-2xs text-ink-faint">{s.detail}</div>
                  </div>
                  <StatusPill tone={tone} dot={false}>
                    {s.status}
                  </StatusPill>
                </li>
              );
            })}
          </ul>
        </Panel>
      </div>

      {/* deployment note */}
      <Panel className="mt-3">
        <PanelHeader title="Deployment" sub="Local-first software project" icon={<ShieldCheck className="h-4 w-4" />} />
        <div className="grid gap-4 p-4 md:grid-cols-2">
          <div>
            <div className="eyebrow mb-2">Inference Mode</div>
            <p className="text-xs leading-relaxed text-ink-muted">
              Configure local Ollama or Transformers models before requesting summaries.
              Source-term review and literal field extraction use the supplied text.
              Missing models produce an availability error; text retrieval uses the configured local embedding backend.
            </p>
          </div>
          <div>
            <div className="eyebrow mb-2">Processing policy</div>
            <p className="text-xs leading-relaxed text-ink-muted">
              Read the active provider policy in Security Center. Host firewalls and
              access controls govern network exposure; application restrictions alone do not isolate the host.
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function Gauge2({
  label,
  value,
  unit,
  icon,
}: {
  label: string;
  value: number | null;
  unit: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-[3px] border border-line bg-surface-inset p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="eyebrow">{label}</span>
        <span className="text-signal">{icon}</span>
      </div>
      <div className="mb-2 font-display text-2xl font-bold text-ink">
        {value === null ? "—" : value.toFixed(0)}
        {value === null ? null : <span className="text-sm text-ink-muted">{unit}</span>}
      </div>
      <Meter value={value ?? 0} tone={(value ?? 0) > 85 ? "caution" : "signal"} />
    </div>
  );
}
