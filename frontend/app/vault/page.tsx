"use client";

import { useEffect, useRef, useState } from "react";
import {
  Panel,
  PanelHeader,
  PageTitle,
  StatusPill,
  SourceChip,
} from "@/components/ui";
import { documents as seed, formatBytes } from "@/lib/data";
import { useLive, fetchAnalysisCatalog, fetchDocuments } from "@/lib/live";
import { api, type AnalysisMode } from "@/lib/api";
import type { KDocument, ProcessState } from "@/lib/types";
import { sampleAnalysisCatalog } from "@/lib/profiles";
import { cn } from "@/lib/utils";
import {
  UploadCloud,
  Lock,
  FileText,
  Check,
  Loader2,
  ShieldCheck,
} from "lucide-react";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.txt,.docx,.csv,.py";
const MAX = 25 * 1024 * 1024;

export default function VaultPage() {
  const { data: liveDocs, source } = useLive(fetchDocuments, seed);
  const { data: analysisCatalog } = useLive(fetchAnalysisCatalog, sampleAnalysisCatalog);
  const [docs, setDocs] = useState<KDocument[]>(seed);
  const [profile, setProfile] = useState("general");
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("risk_review");
  const [uploaded, setUploaded] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Adopt live documents once, unless the user has already uploaded locally.
  useEffect(() => {
    if (!uploaded) setDocs(liveDocs);
  }, [liveDocs, uploaded]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const f = files[0];
    if (f.size > MAX) {
      setNotice(`Rejected: ${f.name} exceeds 25 MB size limit.`);
      return;
    }
    const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
    if (
      !["pdf", "png", "jpg", "jpeg", "txt", "docx", "csv", "py"].includes(ext)
    ) {
      setNotice(`Rejected: .${ext} is not an allowed file type.`);
      return;
    }
    const id = `doc-${Date.now()}`;
    const fresh: KDocument = {
      id,
      name: f.name.replace(/[^a-zA-Z0-9._-]/g, "_"), // path-traversal-safe display name
      type: ext.toUpperCase(),
      sizeBytes: f.size,
      pages: 1,
      classification: "CONFIDENTIAL",
      ocr: "running",
      embedding: "pending",
      indexed: "pending",
      lastProcessed: "processing…",
      accessLevel: "Eng-L2",
      chunks: 0,
    };
    setUploaded(true);
    try {
      const stored = await api.uploadDocument(f);
      fresh.id = String(stored.id);
      fresh.name = stored.filename ?? fresh.name;
      setNotice(
        `${fresh.name} stored on the local backend. You can analyze it below.`,
      );
    } catch (error) {
      setNotice(
        `Upload failed: ${error instanceof Error ? error.message : "backend unavailable"}`,
      );
      return;
    }
    setDocs((d) => [fresh, ...d]);
    setNotice(
      `${fresh.name} stored locally · OCR started (no external upload).`,
    );
    const localId = fresh.id;

    // Keep the local status animation while the backend indexes the file.
    const stages: Array<
      [keyof Pick<KDocument, "ocr" | "embedding" | "indexed">, number]
    > = [
      ["ocr", 1200],
      ["embedding", 2400],
      ["indexed", 3400],
    ];
    stages.forEach(([stage, delay]) => {
      setTimeout(() => {
        setDocs((list) =>
          list.map((doc) => {
            if (doc.id !== localId) return doc;
            const upd: Partial<KDocument> = { [stage]: "done" as ProcessState };
            if (stage === "embedding") upd.embedding = "done";
            const next = stages[stages.findIndex((s) => s[0] === stage) + 1];
            if (next) (upd as any)[next[0]] = "running";
            if (stage === "indexed") {
              upd.lastProcessed = new Date().toLocaleTimeString("en-GB", {
                hour12: false,
              });
              upd.chunks = 42;
            }
            return { ...doc, ...upd };
          }),
        );
      }, delay);
    });
  }

  return (
    <div>
      <PageTitle eyebrow="Encrypted On-Premise Storage" title="Document Vault">
        <div className="flex items-center gap-2">
          <SourceChip source={source} />
          <StatusPill tone="signal" dot={false}>
            <Lock className="h-3 w-3" /> Local Only
          </StatusPill>
        </div>
      </PageTitle>

      {/* Upload */}
      <Panel className="mb-3">
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFiles(e.dataTransfer.files);
          }}
          className="grid-bg flex flex-col items-center justify-center gap-2 px-6 py-8 text-center"
        >
          <UploadCloud className="h-7 w-7 text-signal" />
          <p className="text-sm text-ink">Drop a document to ingest, or</p>
          <button
            onClick={() => inputRef.current?.click()}
            className="btn btn-primary"
          >
            Upload Document
          </button>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
          <p className="font-mono text-2xs text-ink-faint">
            PDF · PNG · JPG · TXT · DOCX · CSV · PY — max 25 MB · stays on this
            appliance
          </p>
          {notice && (
            <p className="mt-1 rounded-[3px] border border-signal/30 bg-signal/[0.06] px-3 py-1.5 font-mono text-2xs text-signal">
              {notice}
            </p>
          )}
        </div>
      </Panel>

      <Panel className="mb-3">
        <PanelHeader title="Analysis settings" sub="Choose a domain profile and task for document analysis" />
        <div className="grid gap-3 p-4 sm:grid-cols-2">
          <label className="block">
            <span className="eyebrow mb-1 block">Domain profile</span>
            <select
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              className="w-full rounded-[3px] border border-line bg-surface-inset px-3 py-2 text-xs text-ink outline-none focus:border-signal/50"
            >
              {analysisCatalog.profiles.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
            <span className="mt-1 block text-2xs text-ink-faint">
              {analysisCatalog.profiles.find((item) => item.id === profile)?.description}
            </span>
          </label>
          <label className="block">
            <span className="eyebrow mb-1 block">Analysis mode</span>
            <select
              value={analysisMode}
              onChange={(e) => setAnalysisMode(e.target.value as AnalysisMode)}
              className="w-full rounded-[3px] border border-line bg-surface-inset px-3 py-2 text-xs text-ink outline-none focus:border-signal/50"
            >
              {analysisCatalog.analysis_modes.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
            <span className="mt-1 block text-2xs text-ink-faint">
              {analysisCatalog.analysis_modes.find((item) => item.id === analysisMode)?.description}
            </span>
          </label>
        </div>
      </Panel>

      {/* Table */}
      <Panel>
        <PanelHeader
          title="Vault Contents"
          sub={`${docs.length} documents · encrypted at rest`}
          icon={<FileText className="h-4 w-4" />}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line font-mono text-2xs uppercase tracking-wider text-ink-faint">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Classification</th>
                <th className="px-3 py-2 font-medium">Pages</th>
                <th className="px-3 py-2 font-medium">Processing</th>
                <th className="px-3 py-2 font-medium">Access</th>
                <th className="px-3 py-2 font-medium">Last Processed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {docs.map((d) => (
                <tr key={d.id} className="hover:bg-surface-raised">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-ink-faint" />
                      <span className="text-ink">{d.name}</span>
                    </div>
                    <span className="font-mono text-2xs text-ink-faint">
                      {formatBytes(d.sizeBytes)} · {d.chunks} chunks
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-ink-muted">
                    {d.type}
                  </td>
                  <td className="px-3 py-2.5">
                    <StatusPill
                      tone={
                        d.classification === "CONFIDENTIAL" ||
                        d.classification === "RESTRICTED"
                          ? "danger"
                          : "info"
                      }
                      dot={false}
                    >
                      {d.classification}
                    </StatusPill>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-ink-muted">
                    {d.pages}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <Stage label="OCR" state={d.ocr} />
                      <Stage label="EMB" state={d.embedding} />
                      <Stage label="IDX" state={d.indexed} />
                    </div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-2xs text-ink-muted">
                    {d.accessLevel}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-2xs text-ink-muted">
                    <div>{d.lastProcessed}</div>
                    {/^[0-9]+$/.test(d.id) && (
                      <button
                        onClick={async () => {
                          setNotice(`Analyzing ${d.name} locally. First model use can take a minute; this notice will update when finished.`);
                          try {
                            const title = analysisMode === "risk_review"
                              ? `Review ${d.name}`
                              : analysisMode === "summary"
                                ? `Summarize ${d.name}`
                                : `Extract fields from ${d.name}`;
                            const description = analysisMode === "risk_review"
                              ? "Review this document for risks and support each finding with source evidence."
                              : analysisMode === "summary"
                                ? "Summarize the document's purpose, key points, decisions, and open questions."
                                : "Extract dates, equipment identifiers, and measurements with exact source excerpts.";
                            const result = await api.analyzeDocument(
                              d.id,
                              title,
                              description,
                              profile,
                              analysisMode,
                            );
                            const outcome = analysisMode === "summary"
                              ? "summary generated"
                              : analysisMode === "extract_fields"
                                ? `${result.run.findings.length} field(s) extracted`
                                : `${result.run.findings.length} risk finding(s) recorded`;
                            setNotice(
                              `Analysis finished: ${outcome}. Run #${result.run.run.id} is in Agent Runs.`,
                            );
                          } catch (error) {
                            setNotice(
                              `Analysis failed: ${error instanceof Error ? error.message : "backend unavailable"}`,
                            );
                          }
                        }}
                        className="mt-1 text-signal hover:underline"
                      >
                        Analyze document
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-1.5 border-t border-line px-4 py-2.5 font-mono text-2xs text-ink-muted">
          <ShieldCheck className="h-3.5 w-3.5 text-signal" /> No document is
          transmitted to any external service. OCR & embedding run locally.
        </div>
      </Panel>
    </div>
  );
}

function Stage({ label, state }: { label: string; state: ProcessState }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-mono text-2xs",
        state === "done"
          ? "text-verified"
          : state === "running"
            ? "text-signal"
            : "text-ink-faint",
      )}
    >
      {state === "done" ? (
        <Check className="h-3 w-3" />
      ) : state === "running" ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <span className="h-1.5 w-1.5 rounded-full bg-ink-faint/50" />
      )}
      {label}
    </span>
  );
}
