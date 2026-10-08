"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const AXIS = "#777c70";
const GRID = "#d1ccbd";

const tasksTrend = [
  { d: "Mon", tasks: 22 },
  { d: "Tue", tasks: 31 },
  { d: "Wed", tasks: 26 },
  { d: "Thu", tasks: 38 },
  { d: "Fri", tasks: 34 },
  { d: "Sat", tasks: 18 },
  { d: "Sun", tasks: 18 },
];

const modelUsage = [
  { m: "qwen3:8b", n: 74, c: "#c94f30" },
  { m: "llama3.2:3b", n: 52, c: "#3f7051" },
  { m: "llava:7b", n: 38, c: "#a66c1c" },
  { m: "nomic-embed", n: 23, c: "#426d76" },
];

function TipBox({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[3px] border border-line-strong bg-surface-raised px-2.5 py-1.5 shadow-panel">
      <div className="font-mono text-2xs text-ink-faint">{label}</div>
      <div className="font-mono text-xs text-ink">
        {payload[0].value}
        {unit}
      </div>
    </div>
  );
}

export function TasksTrendChart() {
  return (
    <ResponsiveContainer width="100%" height={140}>
      <AreaChart data={tasksTrend} margin={{ top: 6, right: 10, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="taskFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#c94f30" stopOpacity={0.32} />
            <stop offset="100%" stopColor="#c94f30" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="d" stroke={AXIS} tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }} axisLine={{ stroke: GRID }} tickLine={false} />
        <YAxis stroke={AXIS} tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} width={30} domain={[0, 40]} ticks={[0, 20, 40]} />
        <Tooltip content={<TipBox unit=" tasks" />} cursor={{ stroke: GRID }} />
        <Area type="monotone" dataKey="tasks" stroke="#c94f30" strokeWidth={2} fill="url(#taskFill)" isAnimationActive={false} dot={{ r: 2, fill: "#c94f30" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ModelUsageChart() {
  return (
    <ResponsiveContainer width="100%" height={140}>
      <BarChart data={modelUsage} layout="vertical" margin={{ top: 2, right: 12, left: 8, bottom: 2 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="m"
          stroke={AXIS}
          tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
          axisLine={false}
          tickLine={false}
          width={70}
        />
        <Tooltip content={<TipBox unit=" runs" />} cursor={{ fill: "#e2ddd0" }} />
        <Bar dataKey="n" radius={[0, 2, 2, 0]} barSize={14} isAnimationActive={false}>
          {modelUsage.map((e) => (
            <Cell key={e.m} fill={e.c} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
