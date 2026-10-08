import { User, Shield, Bot, Cpu, Database, FileCheck2, ArrowDown } from "lucide-react";

const stages = [
  { label: "User", sub: "document request", icon: User, tone: "text-ink" },
  { label: "KAVACH AI", sub: "security · router · planner", icon: Shield, tone: "text-signal" },
  { label: "Local Agents", sub: "8 specialised agents", icon: Bot, tone: "text-signal" },
  { label: "Local Models", sub: "open-weight, on GPU", icon: Cpu, tone: "text-signal" },
  { label: "Local Knowledge Base", sub: "RAG · vector store", icon: Database, tone: "text-signal" },
  { label: "Deliverable", sub: "verified · human-reviewed", icon: FileCheck2, tone: "text-verified" },
];

export function ArchitectureFlow() {
  return (
    <div className="flex flex-col items-stretch gap-1">
      {stages.map((s, i) => {
        const Icon = s.icon;
        return (
          <div key={s.label}>
            <div className="flex items-center gap-3 rounded-[3px] border border-line bg-surface-inset px-3 py-2.5">
              <span className={`grid h-8 w-8 place-items-center rounded-[3px] border border-line-strong bg-surface ${s.tone}`}>
                <Icon className="h-4 w-4" />
              </span>
              <div className="flex-1">
                <div className="font-mono text-xs font-semibold uppercase tracking-wide text-ink">{s.label}</div>
                <div className="text-2xs text-ink-muted">{s.sub}</div>
              </div>
              <span className="font-mono text-2xs text-ink-faint">{String(i + 1).padStart(2, "0")}</span>
            </div>
            {i < stages.length - 1 && (
              <div className="flex justify-center py-0.5">
                <ArrowDown className="h-3.5 w-3.5 text-signal/50" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
