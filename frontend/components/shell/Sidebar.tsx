"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { nav } from "./nav";
import { cn } from "@/lib/utils";
import { systemStatus } from "@/lib/data";
import { usePolledSystem } from "@/lib/live";
import { ShieldHalf } from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const liveSystem = usePolledSystem(5000);
  const gpuPct = liveSystem?.gpu ?? systemStatus.gpu;
  const gpuLabel = !liveSystem
    ? "SAMPLE GPU"
    : liveSystem.gpuSource === "hardware"
      ? "LOCAL GPU"
      : "GPU (SIM)";
  const vramLabel =
    liveSystem?.vramUsedGb != null && liveSystem?.vramTotalGb != null
      ? `${liveSystem.vramUsedGb} / ${liveSystem.vramTotalGb} GB`
      : "sample";
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-14 flex-col border-r border-rail-line bg-rail text-rail-ink shadow-[8px_0_24px_-20px_rgba(10,16,12,0.7)] md:w-[236px]">
      {/* Brand */}
      <div className="flex items-center justify-center gap-3 border-b border-rail-line px-2 py-4 md:justify-start md:px-4">
        <div className="relative grid h-9 w-9 place-items-center rounded-[2px] border border-rail-accent/55 bg-rail-accent/15">
          <ShieldHalf className="h-5 w-5 text-rail-accent" />
          <span className="absolute -right-1 -top-1 h-2 w-2 animate-blip rounded-full bg-rail-accent shadow-glow" />
        </div>
        <div className="hidden leading-tight md:block">
          <div className="font-display text-lg font-bold uppercase tracking-[0.08em] text-rail-ink">
            KAVACH<span className="text-rail-accent"> AI</span>
          </div>
          <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-rail-muted">
            Field System · 01
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-1 py-3 md:px-2">
        <p className="eyebrow hidden px-2 pb-2 text-rail-faint md:block">Workspace / 01</p>
        <ul className="space-y-0.5">
          {nav.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center justify-center gap-3 rounded-[3px] border border-transparent px-2.5 py-2 transition-colors md:justify-start",
                    active
                      ? "border-rail-accent/55 bg-rail-accent/15 text-rail-ink"
                      : "text-rail-muted hover:bg-rail-raised hover:text-rail-ink",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4",
                      active
                        ? "text-rail-accent"
                        : "text-rail-faint group-hover:text-rail-ink",
                    )}
                  />
                  <span className="hidden flex-1 text-sm md:block">
                    {item.label}
                  </span>
                  <span
                    className={cn(
                      "hidden font-mono text-2xs md:block",
                      active ? "text-rail-accent" : "text-rail-faint",
                    )}
                  >
                    {item.code}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Live system rail */}
      <div className="hidden border-t border-rail-line px-3 py-3 md:block">
        <div className="mb-2 flex items-center justify-between">
          <span className="eyebrow text-rail-faint">Local node</span>
          <span className="pill border-rail-accent/50 bg-rail-accent/15 text-rail-accent">
            <span className="led animate-blip bg-rail-accent" />
            READY
          </span>
        </div>
        <div className="mb-2">
          <div className="mb-1 flex items-center justify-between font-mono text-2xs text-rail-muted">
            <span>{gpuLabel}</span>
            <span className="text-rail-ink">{gpuPct}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-rail-raised">
            <div
              className="h-full rounded-full bg-rail-meter"
              style={{ width: `${gpuPct}%` }}
            />
          </div>
          <div className="mt-1 font-mono text-2xs text-rail-faint">
            VRAM {vramLabel}
          </div>
        </div>
        <ul className="grid grid-cols-2 gap-1">
          {systemStatus.services.slice(0, 8).map((s) => (
            <li
              key={s.name}
              className="flex items-center gap-1.5 font-mono text-2xs text-rail-muted"
            >
              <span
                className={cn(
                  "led",
                  s.status === "AIR-GAPPED" ? "bg-[#c49342]" : "bg-[#75a17d]",
                )}
              />
              <span className="truncate" title={`${s.name} · ${s.detail}`}>
                {s.name}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
