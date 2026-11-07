import { PageTitle } from "@/components/ui";
import { LiveRuns } from "@/components/viz/LiveRuns";
export default function RunsPage() {
  return <div><PageTitle eyebrow="Execution monitoring" title="Agent Runs" /><LiveRuns /></div>;
}
