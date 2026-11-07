"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type LiveRunDetail } from "@/lib/api";
import { PageTitle, Panel } from "@/components/ui";
import { RunDetail } from "@/components/viz/LiveRuns";
export default function RunPage({ params }: { params: { id: string } }) {
  const [detail, setDetail] = useState<LiveRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      if (!/^\d+$/.test(params.id)) throw new Error("Invalid run ID");
      setDetail(await api.run(Number(params.id)));
    } catch (err) { setError(err instanceof Error ? err.message : "Run unavailable"); }
  }, [params.id]);
  useEffect(() => { load(); }, [load]);
  async function review(id: number, decision: "approve" | "reject") {
    try { await api.reviewFinding(id, decision); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Review failed"); }
  }
  return <div><PageTitle eyebrow="Execution details" title={`Run #${params.id}`} />
    {error && <p role="alert" className="text-danger">{error}</p>}
    {detail ? <Panel className="p-4"><p className="mb-4 text-sm">Status: {detail.run.status}</p><RunDetail detail={detail} onReview={review} /></Panel> : !error && <p>Loading run...</p>}
  </div>;
}
