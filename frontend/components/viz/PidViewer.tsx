"use client";

import { useState } from "react";
import { pidRegions, evidence } from "@/lib/data";
import type { PidRegion } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ScanLine, Loader2 } from "lucide-react";
import { Tag } from "@/components/ui";

const kindColor: Record<PidRegion["kind"], string> = {
  pump: "#c94f30",
  valve: "#a66c1c",
  tank: "#3f7051",
  exchanger: "#426d76",
  instrument: "#7a8176",
  line: "#777c70",
};

type Phase = "idle" | "scanning" | "done";

export function PidViewer() {
  const [phase, setPhase] = useState<Phase>("done");
  const [selected, setSelected] = useState<string | null>(null);

  function analyze() {
    setPhase("scanning");
    setSelected(null);
    setTimeout(() => setPhase("done"), 2200);
  }

  const region = pidRegions.find((r) => r.id === selected);
  const linkedEv = region?.evidenceId ? evidence.find((e) => e.id === region.evidenceId) : undefined;

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div className="panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span className="eyebrow">Unit_4_Plant_PID.pdf · sheet 1/3</span>
          </div>
          <button onClick={analyze} disabled={phase === "scanning"} className="btn btn-primary px-2.5 py-1.5">
            {phase === "scanning" ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Analyzing
              </>
            ) : (
              <>
                <ScanLine className="h-3.5 w-3.5" /> Analyze Diagram
              </>
            )}
          </button>
        </div>

        <div className="relative bg-surface-inset">
          <svg viewBox="0 0 100 92" className="w-full" role="img" aria-label="Unit 4 P&ID schematic">
            {/* drawing grid */}
            <defs>
              <pattern id="pgrid" width="4" height="4" patternUnits="userSpaceOnUse">
                <path d="M4 0 H0 V4" fill="none" stroke="#c9c3b5" strokeWidth="0.3" />
              </pattern>
            </defs>
            <rect x="0" y="0" width="100" height="92" fill="url(#pgrid)" />

            {/* ---- pipelines ---- */}
            <g stroke="#596258" strokeWidth="0.7" fill="none" strokeLinecap="round">
              {/* tank -> suction header */}
              <path d="M21 47 H26 V63 H30" />
              <path d="M26 63 V81 H30" />
              {/* pump discharge -> exchanger */}
              <path d="M39 63 H45 V48 H50" />
              <path d="M39 81 H45" />
              {/* exchanger -> header -> valve */}
              <path d="M68 48 H72 V25 H74" />
              <path d="M82 25 H92 V60" />
            </g>
            {/* flow direction ticks (animated when analyzed) */}
            {phase !== "idle" && (
              <g stroke={kindColor.pump} strokeWidth="0.8" strokeDasharray="1.5 2.5" className="animate-flow" fill="none">
                <path d="M21 47 H26 V63 H30" />
                <path d="M39 63 H45 V48 H50" />
                <path d="M68 48 H72 V25 H74" />
              </g>
            )}

            {/* ---- equipment symbols ---- */}
            {/* T-101 feed tank */}
            <g>
              <path d="M6 34 Q6 30 10.5 30 H16.5 Q21 30 21 34 V64 H6 Z" fill="#f2efe6" stroke="#3f7051" strokeWidth="0.6" />
              <text x="13.5" y="50" textAnchor="middle" className="fill-ink font-mono" fontSize="3">T-101</text>
            </g>
            {/* P-101 / P-102 pumps (circle + discharge triangle) */}
            {[
              { cx: 34.5, cy: 63, id: "P-101" },
              { cx: 34.5, cy: 81, id: "P-102" },
            ].map((p) => (
              <g key={p.id}>
                <circle cx={p.cx} cy={p.cy} r="4.5" fill="#f2efe6" stroke={kindColor.pump} strokeWidth="0.6" />
                <path d={`M${p.cx} ${p.cy - 4.5} L${p.cx + 4} ${p.cy - 4.5} L${p.cx} ${p.cy}`} fill={kindColor.pump} opacity="0.5" />
                <text x={p.cx} y={p.cy + 1} textAnchor="middle" className="fill-ink font-mono" fontSize="2.6">{p.id}</text>
              </g>
            ))}
            {/* HX-301 exchanger */}
            <g>
              <rect x="50" y="40" width="18" height="16" rx="1" fill="#f2efe6" stroke={kindColor.exchanger} strokeWidth="0.6" />
              <line x1="50" y1="44" x2="68" y2="44" stroke={kindColor.exchanger} strokeWidth="0.35" />
              <line x1="50" y1="52" x2="68" y2="52" stroke={kindColor.exchanger} strokeWidth="0.35" />
              <text x="59" y="49.5" textAnchor="middle" className="fill-ink font-mono" fontSize="2.8">HX-301</text>
            </g>
            {/* V-204 relief valve (bowtie) */}
            <g>
              <path d="M74 20 L82 30 L82 20 L74 30 Z" fill="#f2efe6" stroke={kindColor.valve} strokeWidth="0.6" />
              <text x="78" y="17" textAnchor="middle" className="fill-caution font-mono" fontSize="2.6">V-204</text>
            </g>
            {/* PT-104 instrument */}
            <g>
              <line x1="13.5" y1="30" x2="23.5" y2="19.5" stroke="#777c70" strokeWidth="0.4" strokeDasharray="1 1" />
              <circle cx="23.5" cy="19.5" r="3.5" fill="#f2efe6" stroke={kindColor.instrument} strokeWidth="0.5" />
              <text x="23.5" y="20.5" textAnchor="middle" className="fill-ink-muted font-mono" fontSize="2.2">PT</text>
            </g>

            {/* ---- detection overlays ---- */}
            {phase === "done" &&
              pidRegions.map((r) => {
                const active = selected === r.id;
                return (
                  <g key={r.id} className="animate-fadein cursor-pointer" onClick={() => setSelected(active ? null : r.id)}>
                    <rect
                      x={r.x}
                      y={r.y}
                      width={r.w}
                      height={r.h}
                      rx="0.6"
                      fill={active ? `${kindColor[r.kind]}22` : "transparent"}
                      stroke={kindColor[r.kind]}
                      strokeWidth={active ? "0.8" : "0.45"}
                      strokeDasharray={active ? "0" : "1.4 1"}
                      opacity={active ? 1 : 0.8}
                    />
                    {/* corner ticks */}
                    <path
                      d={`M${r.x} ${r.y + 1.5} V${r.y} H${r.x + 1.5} M${r.x + r.w - 1.5} ${r.y} H${r.x + r.w} V${r.y + 1.5}`}
                      stroke={kindColor[r.kind]}
                      strokeWidth="0.5"
                      fill="none"
                    />
                    <text x={r.x} y={r.y - 0.8} className="font-mono" fontSize="2.1" fill={kindColor[r.kind]}>
                      {r.id}
                    </text>
                  </g>
                );
              })}

            {/* scanning sweep */}
            {phase === "scanning" && (
              <g>
                <rect x="0" y="0" width="100" height="92" fill="url(#pgrid)" opacity="0" />
                <rect className="animate-sweep" x="0" y="-8" width="100" height="8" fill={kindColor.pump} opacity="0.14" />
                <line className="animate-sweep" x1="0" y1="0" x2="100" y2="0" stroke={kindColor.pump} strokeWidth="0.5" opacity="0.8" />
              </g>
            )}
          </svg>
        </div>
      </div>

      {/* detection panel */}
      <div className="panel flex flex-col">
        <div className="border-b border-line px-4 py-2.5">
          <span className="eyebrow">Detected Objects</span>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          {phase === "scanning" ? (
            <div className="flex h-full items-center justify-center py-10 text-center">
              <div>
                <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-signal" />
                <p className="font-mono text-2xs text-ink-muted">Vision model segmenting P&ID regions…</p>
              </div>
            </div>
          ) : (
            <ul className="space-y-1.5">
              {pidRegions.map((r) => {
                const active = selected === r.id;
                return (
                  <li key={r.id}>
                    <button
                      onClick={() => setSelected(active ? null : r.id)}
                      className={cn(
                        "flex w-full items-center gap-2.5 rounded-[3px] border px-2.5 py-2 text-left transition-colors",
                        active ? "border-signal/40 bg-signal/[0.07]" : "border-line hover:border-line-strong",
                      )}
                    >
                      <span className="led" style={{ background: kindColor[r.kind] }} />
                      <span className="font-mono text-xs font-semibold text-ink">{r.id}</span>
                      <span className="flex-1 truncate text-2xs text-ink-muted">{r.label}</span>
                      <span className="font-mono text-2xs uppercase text-ink-faint">{r.kind}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* linked evidence for selected region */}
        {region && (
          <div className="animate-fadein border-t border-line bg-surface-inset p-3">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="font-mono text-xs font-semibold text-signal">{region.id}</span>
              <Tag>{region.kind}</Tag>
            </div>
            <p className="mb-2 text-2xs text-ink-muted">{region.note}</p>
            {linkedEv ? (
              <div className="rounded-[3px] border border-line bg-surface p-2">
                <div className="mb-1 font-mono text-2xs text-ink-faint">
                  ↳ {linkedEv.source} · p.{linkedEv.page} · {linkedEv.relevance}%
                </div>
                <p className="text-2xs leading-relaxed text-ink-muted">“{linkedEv.excerpt}”</p>
              </div>
            ) : (
              <p className="font-mono text-2xs text-ink-faint">no linked corpus evidence</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
