"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Panel, PanelHeader, PageTitle, SourceChip, StatusPill } from "@/components/ui";
import { api, ApiError, type AnalysisJob, type AnalysisMode, type LiveRunDetail } from "@/lib/api";
import { useLive, fetchDocuments, fetchAnalysisCatalog } from "@/lib/live";
import { defaultAnalysisCatalog, useCases } from "@/lib/profiles";
import { RunDetail } from "@/components/viz/LiveRuns";
import { AnalysisFlow } from "@/components/viz/AnalysisFlow";

const SAVED_JOB = "kavach.workbench.analysisJob";
function rememberJob(id: string | null) {
  try { if (id) localStorage.setItem(SAVED_JOB, id); else localStorage.removeItem(SAVED_JOB); } catch { /* Storage is optional. */ }
}
function reveal(element: HTMLElement | null) {
  element?.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

export default function WorkbenchPage() {
  const { data: documents, source } = useLive(fetchDocuments, []);
  const { data: catalog } = useLive(fetchAnalysisCatalog, defaultAnalysisCatalog);
  const [documentId, setDocumentId] = useState("");
  const [profile, setProfile] = useState("general");
  const [mode, setMode] = useState<AnalysisMode>("risk_review");
  const [task, setTask] = useState("Review this document for issues, missing information, and next actions. Cite the source for each finding.");
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<LiveRunDetail | null>(null);
  const submissionLock = useRef(false);
  const restoring = useRef(false);
  const flowRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const busy = submitting || Boolean(jobId && !job) || job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    try {
      const requested = new URLSearchParams(window.location.search).get("job");
      const saved = requested || localStorage.getItem(SAVED_JOB);
      if (saved) { restoring.current = true; rememberJob(saved); setJobId(saved); }
    } catch { /* A fresh analysis still works without browser storage. */ }
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const snapshot = await api.analysisJob(jobId!);
        if (disposed) return;
        setJob(snapshot);
        setConnectionError(null);
        if (restoring.current) {
          setDocumentId(String(snapshot.document_id)); setProfile(snapshot.request.profile);
          setMode(snapshot.request.analysis_mode); setTask(snapshot.request.description || snapshot.request.title);
          restoring.current = false;
        }
        if (snapshot.result) setResult(snapshot.result.run);
        if (snapshot.status === "queued" || snapshot.status === "running") timer = setTimeout(poll, 1000);
      } catch (err) {
        if (disposed) return;
        if (err instanceof ApiError && err.status === 404) {
          rememberJob(null); setJobId(null); setJob(null);
          setError("The previous analysis job is no longer available. You can start a new analysis.");
        } else {
          setConnectionError("Progress connection interrupted. Reconnecting to the same saved analysis...");
          timer = setTimeout(poll, 2000);
        }
      }
    }
    void poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [jobId]);

  useEffect(() => { if (job?.status === "queued" || job?.status === "running") reveal(flowRef.current); }, [job?.id]);
  useEffect(() => { if (result) reveal(resultRef.current); }, [result?.run.id]);

  useEffect(() => {
    if (documents.length && !documents.some((d) => d.id === documentId)) setDocumentId(documents[0].id);
  }, [documents, documentId]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("profile");
    const preset = useCases.find((item) => item.profile === requested);
    if (preset) { setProfile(preset.profile); setMode(preset.mode); setTask(preset.request); }
    const requestedMode = params.get("mode");
    if (requestedMode === "risk_review" || requestedMode === "summary" || requestedMode === "extract_fields") {
      setMode(requestedMode);
      const example = useCases.find((item) => item.mode === requestedMode);
      if (example) setTask(requestedMode === "risk_review"
        ? "Review this document for issues, missing information, and next actions. Cite the source for each finding."
        : example.request);
    }
  }, []);

  async function run(planner: boolean) {
    if (submissionLock.current) return;
    submissionLock.current = true;
    setSubmitting(true); setError(null); setResult(null); setConnectionError(null);
    try {
      const snapshot = await api.startAnalysis(documentId, task, profile, mode, planner);
      rememberJob(snapshot.id); setJob(snapshot); setJobId(snapshot.id);
      const url = new URL(window.location.href);
      url.searchParams.set("job", snapshot.id);
      window.history.replaceState(null, "", url);
      if (snapshot.result) setResult(snapshot.result.run);
    } catch (err) { setError(err instanceof Error ? err.message : "Analysis failed"); }
    finally { setSubmitting(false); submissionLock.current = false; }
  }
  async function review(id: number, decision: "approve" | "reject") {
    if (!result) return;
    try { await api.reviewFinding(id, decision); setResult(await api.run(result.run.id)); }
    catch (err) { setError(err instanceof Error ? err.message : "Review failed"); }
  }
  const disabled = busy || source !== "live" || !documents.some((d) => d.id === documentId) || !task.trim();
  return <div>
    <PageTitle eyebrow="Document analysis" title="Workbench"><SourceChip source={source} /></PageTitle>
    <Panel><PanelHeader title="Analyze a stored document" right={<Link href="/vault" className="text-sm text-signal">Upload a document</Link>} />
      <div className="space-y-4 p-4">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {useCases.map((item) => <button key={item.profile} disabled={busy} onClick={() => { setProfile(item.profile); setMode(item.mode); setTask(item.request); }} className="rounded border border-line p-3 text-left hover:border-signal">
            <span className="block text-sm font-semibold">{item.title}</span><span className="text-xs text-ink-muted">{item.description}</span>
          </button>)}
        </div>
        <label className="block"><span className="eyebrow block">Source document</span>
          <select disabled={busy} value={documentId} onChange={(e) => setDocumentId(e.target.value)} className="w-full rounded border border-line bg-surface p-2">
            {!documents.length && <option value="">No documents available</option>}
            {documents.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        {documents.find((d) => d.id === documentId)?.type.match(/^(PNG|JPG|JPEG)$/) && <p className="text-xs text-ink-muted">
          This image will be inspected by the local vision model in every analysis mode. Summary describes the image; Extract fields returns supported literal values from OCR text. Visual observations appear separately from fields and issue matches.
        </p>}
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="eyebrow block">Profile</span><select disabled={busy} value={profile} onChange={(e) => setProfile(e.target.value)} className="w-full rounded border border-line bg-surface p-2">{catalog.profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <label><span className="eyebrow block">Analysis mode</span><select disabled={busy} value={mode} onChange={(e) => setMode(e.target.value as AnalysisMode)} className="w-full rounded border border-line bg-surface p-2">{catalog.analysis_modes.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
        </div>
        <label className="block"><span className="eyebrow block">Analysis request</span><textarea disabled={busy} value={task} onChange={(e) => setTask(e.target.value)} rows={3} maxLength={2000} className="w-full rounded border border-line bg-surface p-2" /></label>
        <div className="flex flex-wrap gap-2"><button disabled={disabled} onClick={() => run(false)} className="btn btn-primary">{busy ? "Processing..." : "Analyze document"}</button><button disabled={disabled} onClick={() => run(true)} className="btn btn-ghost">Run bounded planner</button></div>
        {submitting && <p role="status" className="text-sm text-ink-muted">Starting a saved local analysis...</p>}
        {jobId && !job && <p role="status" className="text-sm text-ink-muted">Restoring your saved analysis...</p>}
        {source === "live" && !documents.length && <p className="text-sm text-ink-muted">Upload your first document in the Document Vault.</p>}
        {source === "unavailable" && <p role="alert" className="text-sm text-danger">Backend unavailable. Connect the local service to analyze documents.</p>}
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      </div>
    </Panel>
    {job && <div ref={flowRef} className="mt-4 scroll-mt-20"><AnalysisFlow job={job} /></div>}
    {connectionError && <p role="status" className="mt-3 rounded border border-caution/30 p-3 text-sm text-caution">{connectionError}</p>}
    {result && <div ref={resultRef} className="mt-4 scroll-mt-20"><Panel>
      <PanelHeader title={`Analysis results / Run #${result.run.id}`} sub={job?.document?.filename}
        right={<StatusPill tone={result.run.status === "awaiting_review" ? "caution" : result.run.status === "halted" ? "danger" : "verified"}>
          {result.run.status.replaceAll("_", " ")}
        </StatusPill>} />
      <div className="space-y-5 p-4 sm:p-5">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <ResultStat label="Pages read" value={result.extraction?.page_count ?? "Unavailable"} />
          <ResultStat label="Pages using OCR" value={result.extraction?.ocr_pages ?? "Unavailable"} />
          <ResultStat label={result.run.analysis_mode === "extract_fields" ? "Fields extracted" : "Source matches"} value={result.findings.length} />
          <ResultStat label="Awaiting review" value={result.findings.filter((f) => f.needs_review && f.review_status === "pending").length} />
        </div>
        {result.extraction?.note && <p className="rounded border border-caution/30 p-3 text-xs text-caution">Extraction note: {result.extraction.note}</p>}
        <RunDetail detail={result} onReview={review} showTrace={false} />
        <div className="flex flex-wrap gap-4">
          <Link href={`/runs/${result.run.id}`} className="inline-block text-sm text-signal hover:underline">Open saved run and full execution trace</Link>
          {job && <Link href={`/workbench?job=${job.id}`} className="inline-block text-sm text-signal hover:underline">Saved Workbench result link</Link>}
        </div>
      </div>
    </Panel></div>}
    {job?.status === "error" && job.run_id && <Link href={`/runs/${job.run_id}`} className="mt-3 inline-block text-sm text-signal">Inspect saved error run #{job.run_id}</Link>}
  </div>;
}

function ResultStat({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded border border-line bg-surface-inset p-3"><p className="eyebrow">{label}</p><p className="mt-2 font-display text-2xl font-semibold text-ink">{value}</p></div>;
}
