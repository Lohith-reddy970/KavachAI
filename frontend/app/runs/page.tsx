import Link from "next/link";
import { Panel, PanelHeader, PageTitle, StatusPill } from "@/components/ui";
import { LiveRuns } from "@/components/viz/LiveRuns";
import { runs } from "@/lib/data";
import { Activity, ChevronRight } from "lucide-react";

const statusTone: Record<string, "verified" | "signal" | "caution" | "muted"> = {
  COMPLETED: "verified",
  RUNNING: "signal",
  REVIEW: "caution",
  QUEUED: "muted",
  FAILED: "muted",
};

export default function RunsPage() {
  return (
    <div>
      <PageTitle eyebrow="Execution Monitoring" title="Agent Runs">
        <StatusPill tone="signal" dot={false}>
          {runs.length} runs logged
        </StatusPill>
      </PageTitle>

      <LiveRuns />

      <Panel>
        <PanelHeader title="Run History" icon={<Activity className="h-4 w-4" />} sub="Bundled sample runs · all executions are local" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line font-mono text-2xs uppercase tracking-wider text-ink-faint">
                <th className="px-4 py-2 font-medium">Run ID</th>
                <th className="px-3 py-2 font-medium">Task</th>
                <th className="px-3 py-2 font-medium">Agent</th>
                <th className="px-3 py-2 font-medium">Model</th>
                <th className="px-3 py-2 font-medium">Start</th>
                <th className="px-3 py-2 font-medium">Duration</th>
                <th className="px-3 py-2 font-medium">Verify</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-2 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {runs.map((r) => (
                <tr key={r.id} className="group hover:bg-surface-raised">
                  <td className="px-4 py-3 font-mono text-signal">
                    <Link href={`/runs/${r.id}`}>{r.id}</Link>
                  </td>
                  <td className="max-w-[220px] truncate px-3 py-3 text-ink">{r.task}</td>
                  <td className="px-3 py-3 text-ink-muted">{r.agent}</td>
                  <td className="px-3 py-3 font-mono text-2xs text-ink-muted">{r.model}</td>
                  <td className="px-3 py-3 font-mono text-2xs text-ink-faint">{r.startTime.split(" ")[1]}</td>
                  <td className="px-3 py-3 font-mono text-ink-muted">{(r.durationMs / 1000).toFixed(1)}s</td>
                  <td className="px-3 py-3 font-mono text-ink">{r.verification}%</td>
                  <td className="px-3 py-3">
                    <StatusPill tone={statusTone[r.status]} dot={false}>
                      {r.status}
                    </StatusPill>
                  </td>
                  <td className="px-2 py-3">
                    <Link href={`/runs/${r.id}`}>
                      <ChevronRight className="h-4 w-4 text-ink-faint group-hover:text-signal" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
