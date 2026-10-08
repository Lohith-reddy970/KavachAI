"use client";

import { Cloud, X } from "lucide-react";

/**
 * The signature element: the Data Boundary.
 * Data flows inside a sealed organisation perimeter; the link to external
 * cloud AI is physically severed. This is the whole pitch in one picture.
 */
export function BoundaryDiagram({ compact = false }: { compact?: boolean }) {
  return (
    <div className="relative">
      <svg
        viewBox="0 0 640 300"
        className="w-full"
        role="img"
        aria-label="Data boundary: all processing stays inside the organisation network; external cloud AI is blocked."
      >
        <defs>
          <linearGradient id="flow" x1="0" x2="1">
            <stop offset="0%" stopColor="#c94f30" stopOpacity="0.12" />
            <stop offset="50%" stopColor="#c94f30" stopOpacity="1" />
            <stop offset="100%" stopColor="#c94f30" stopOpacity="0.12" />
          </linearGradient>
          <pattern
            id="dots"
            width="16"
            height="16"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="1" cy="1" r="1" fill="#a69f8f" />
          </pattern>
        </defs>

        {/* Perimeter */}
        <rect
          x="14"
          y="40"
          width="480"
          height="244"
          rx="4"
          fill="url(#dots)"
          opacity="0.5"
        />
        <rect
          x="14"
          y="40"
          width="480"
          height="244"
          rx="4"
          fill="none"
          stroke="#3f7051"
          strokeWidth="1.5"
          strokeDasharray="2 4"
          opacity="0.7"
        />
        {/* corner brackets */}
        {[
          [14, 40, 1, 1],
          [494, 40, -1, 1],
          [14, 284, 1, -1],
          [494, 284, -1, -1],
        ].map(([x, y, sx, sy], i) => (
          <path
            key={i}
            d={`M ${x} ${(y as number) + 16 * (sy as number)} L ${x} ${y} L ${(x as number) + 16 * (sx as number)} ${y}`}
            stroke="#c94f30"
            strokeWidth="2"
            fill="none"
          />
        ))}

        <text
          x="26"
          y="30"
          className="fill-signal font-mono"
          fontSize="11"
          letterSpacing="2"
        >
          ORGANIZATION NETWORK · ON-PREMISE
        </text>

        {/* Internal pipeline nodes */}
        {[
          { x: 60, label: "Documents", sub: "encrypted" },
          { x: 175, label: "KAVACH", sub: "orchestrator" },
          { x: 290, label: "Local Models", sub: "open-weight" },
          { x: 405, label: "Local RAG", sub: "vector db" },
        ].map((n) => (
          <g key={n.label}>
            <rect
              x={n.x}
              y={130}
              width="86"
              height="52"
              rx="3"
              fill="#f8f5ec"
              stroke={n.label === "KAVACH" ? "#c94f30" : "#aaa493"}
              strokeWidth={n.label === "KAVACH" ? 1.6 : 1}
            />
            <text
              x={n.x + 43}
              y={152}
              textAnchor="middle"
              className="fill-ink font-mono"
              fontSize="11"
            >
              {n.label}
            </text>
            <text
              x={n.x + 43}
              y={168}
              textAnchor="middle"
              className="fill-ink-muted font-mono"
              fontSize="8.5"
            >
              {n.sub}
            </text>
          </g>
        ))}

        {/* animated flow lines between nodes */}
        {[146, 261, 376].map((x, i) => (
          <line
            key={i}
            x1={x}
            y1={156}
            x2={x + 29}
            y2={156}
            stroke="url(#flow)"
            strokeWidth="2"
            strokeDasharray="6 6"
            className="animate-flow"
          />
        ))}

        {/* Deliverable output */}
        <line
          x1={491}
          y1={156}
          x2={520}
          y2={156}
          stroke="#c94f30"
          strokeWidth="1.5"
          strokeDasharray="3 3"
        />
        <rect
          x="520"
          y="130"
          width="98"
          height="52"
          rx="3"
          fill="#f8f5ec"
          stroke="#3f7051"
          strokeWidth="1.2"
        />
        <text
          x={569}
          y={152}
          textAnchor="middle"
          className="fill-verified font-mono"
          fontSize="11"
        >
          Deliverable
        </text>
        <text
          x={569}
          y={168}
          textAnchor="middle"
          className="fill-ink-muted font-mono"
          fontSize="8.5"
        >
          stays on-prem
        </text>

        {/* Severed external cloud link */}
        <line
          x1={254}
          y1={130}
          x2={254}
          y2={92}
          stroke="#b73d2b"
          strokeWidth="1.4"
          strokeDasharray="4 4"
          opacity="0.8"
        />
        {/* break marker */}
        <g transform="translate(254 110)">
          <circle r="11" fill="#f8e8e1" stroke="#b73d2b" strokeWidth="1.4" />
          <path
            d="M -5 -5 L 5 5 M 5 -5 L -5 5"
            stroke="#b73d2b"
            strokeWidth="1.8"
          />
        </g>
        <text x={272} y={104} className="fill-danger font-mono" fontSize="9">
          BLOCKED
        </text>
      </svg>

      {/* External cloud, outside the box */}
      {!compact && (
        <div className="pointer-events-none absolute right-3 top-1 flex flex-col items-center">
          <div className="relative grid h-14 w-16 place-items-center rounded-[3px] border border-danger/40 bg-danger/5">
            <Cloud className="h-6 w-6 text-danger/70" />
            <X className="absolute h-7 w-7 text-danger" strokeWidth={2.5} />
          </div>
          <span className="mt-1 font-mono text-2xs uppercase tracking-widest text-danger">
            External AI
          </span>
        </div>
      )}
    </div>
  );
}
