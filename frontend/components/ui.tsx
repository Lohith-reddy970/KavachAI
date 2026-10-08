import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/** Panel — the primary control-room surface. */
export function Panel({
  className,
  children,
  raised,
}: {
  className?: string;
  children: ReactNode;
  raised?: boolean;
}) {
  return <div className={cn(raised ? "panel-raised" : "panel", className)}>{children}</div>;
}

/** PanelHeader — eyebrow-style section head with optional right slot. */
export function PanelHeader({
  title,
  sub,
  icon,
  right,
}: {
  title: string;
  sub?: string;
  icon?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between border-b border-line px-4 py-3">
      <div className="flex items-center gap-2.5">
        {icon ? <span className="text-signal">{icon}</span> : null}
        <div>
          <h3 className="font-display text-base font-semibold uppercase tracking-[0.06em] text-ink">{title}</h3>
          {sub ? <p className="text-2xs text-ink-muted">{sub}</p> : null}
        </div>
      </div>
      {right}
    </div>
  );
}

/** Section title used at the top of each page. */
export function PageTitle({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="eyebrow mb-1 text-signal">{eyebrow}</p>
        <h1 className="font-display text-3xl font-semibold uppercase leading-none tracking-[0.035em] text-ink sm:text-4xl">{title}</h1>
      </div>
      {children}
    </div>
  );
}

type Tone = "signal" | "verified" | "caution" | "danger" | "info" | "muted";
const toneMap: Record<Tone, string> = {
  signal: "border-signal/40 bg-signal/10 text-signal",
  verified: "border-verified/40 bg-verified/10 text-verified",
  caution: "border-caution/40 bg-caution/10 text-caution",
  danger: "border-danger/40 bg-danger/10 text-danger",
  info: "border-info/40 bg-info/10 text-info",
  muted: "border-line-strong bg-surface-inset text-ink-muted",
};
const ledMap: Record<Tone, string> = {
  signal: "bg-signal",
  verified: "bg-verified",
  caution: "bg-caution",
  danger: "bg-danger",
  info: "bg-info",
  muted: "bg-ink-faint",
};

export function StatusPill({
  tone = "muted",
  children,
  dot = true,
  pulse = false,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  dot?: boolean;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("pill", toneMap[tone], className)}>
      {dot ? <span className={cn("led", ledMap[tone], pulse && "animate-blip")} /> : null}
      {children}
    </span>
  );
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="tag">{children}</span>;
}

export function Meter({
  value,
  tone = "signal",
  className,
}: {
  value: number;
  tone?: Tone;
  className?: string;
}) {
  const barTone =
    tone === "danger"
      ? "bg-danger"
      : tone === "caution"
        ? "bg-caution"
        : tone === "verified"
          ? "bg-verified"
          : tone === "info"
            ? "bg-info"
            : "bg-signal";
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-inset", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-500", barTone)}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

/** Indicates whether a panel is showing live backend data or bundled sample data. */
export function SourceChip({ source }: { source: "mock" | "live" }) {
  return source === "live" ? (
    <StatusPill tone="verified" pulse>
      Live Backend
    </StatusPill>
  ) : (
    <StatusPill tone="info" dot={false}>
      Bundled Sample Data
    </StatusPill>
  );
}

export function KeyVal({ k, v, mono = true }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <span className="text-xs text-ink-muted">{k}</span>
      <span className={cn("text-xs text-ink", mono && "font-mono")}>{v}</span>
    </div>
  );
}
