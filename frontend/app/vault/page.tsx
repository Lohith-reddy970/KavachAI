"use client";

import { useEffect, useRef, useState } from "react";
import {
  Panel,
  PanelHeader,
  PageTitle,
  StatusPill,
  SourceChip,
} from "@/components/ui";
import { formatBytes } from "@/lib/utils";
import { useLive, fetchAnalysisCatalog, fetchDocuments } from "@/lib/live";
import { api, type AnalysisMode } from "@/lib/api";
import type { KDocument, ProcessState } from "@/lib/types";
import { defaultAnalysisCatalog } from "@/lib/profiles";
import { cn } from "@/lib/utils";
import { DocumentDeleteDialog, DocumentPreviewDialog } from "@/components/vault/DocumentDialogs";
import { BatchAnalysisPanel } from "@/components/vault/BatchAnalysisPanel";
import {
  UploadCloud,
  Lock,
  FileText,
  Check,
  Loader2,
  ShieldCheck,
  Eye,
  Trash2,
} from "lucide-react";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.txt,.docx,.csv,.py";
const MAX = 25 * 1024 * 1024;

export default function VaultPage() {
  const { data: liveDocs, source } = useLive(fetchDocuments, []);
  const { data: analysisCatalog } = useLive(fetchAnalysisCatalog, defaultAnalysisCatalog);
  const [docs, setDocs] = useState<KDocument[]>([]);
  const [profile, setProfile] = useState("general");
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("risk_review");
  const [locallyChanged, setLocallyChanged] = useState(false);
  const [previewDocument, setPreviewDocument] = useState<KDocument | null>(null);
  const [deleteDocument, setDeleteDocument] = useState<KDocument | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadLock = useRef(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState<{ name: string; status: string; error?: string }[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // A late initial response must not overwrite an upload or resurrect a deleted row.
  useEffect(() => {
    if (!locallyChanged) setDocs(liveDocs);
  }, [liveDocs, locallyChanged]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0 || uploadLock.current) return;
    const entries = Array.from(files);
    if (entries.length > 50) { setNotice("Choose up to 50 files per upload batch."); return; }
    uploadLock.current = true; setUploading(true);
    setUploadResults(entries.map((entry) => ({ name: entry.name, status: "waiting" })));
    let storedCount = 0;
    try {
      for (let index = 0; index < entries.length; index++) {
        const file = entries[index];
        setUploadResults((items) => items.map((item, i) => i === index ? { ...item, status: "uploading" } : item));
        try {
          if (file.size > MAX) throw new Error("Exceeds the 25 MB size limit.");
          const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
          if (!["pdf", "png", "jpg", "jpeg", "txt", "docx", "csv", "py"].includes(ext)) throw new Error(`.${ext} is not an allowed file type.`);
          const stored = await api.uploadDocument(file);
          const fresh: KDocument = { id: String(stored.id), name: stored.filename, type: ext.toUpperCase(), sizeBytes: stored.size_bytes ?? file.size,
            pages: 0, classification: ext === "py" ? "RESTRICTED" : "CONFIDENTIAL", ocr: "pending", embedding: "pending", indexed: "pending", lastProcessed: "not analyzed", accessLevel: "Local", chunks: 0 };
          setLocallyChanged(true); setDocs((items) => [fresh, ...items]);
          setSelectedIds((ids) => [...ids, fresh.id]); storedCount++;
          setUploadResults((items) => items.map((item, i) => i === index ? { ...item, status: "stored" } : item));
        } catch (err) {
          setUploadResults((items) => items.map((item, i) => i === index ? { ...item, status: "failed", error: err instanceof Error ? err.message : "Upload failed." } : item));
        }
      }
      setNotice(`${storedCount}/${entries.length} file(s) stored locally. Successful uploads are selected for batch analysis.`);
    } finally {
      if (inputRef.current) inputRef.current.value = "";
      uploadLock.current = false; setUploading(false);
    }
  }


  return (
    <div>
      <PageTitle eyebrow="Private Local Document Storage" title="Document Vault">
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
          <p className="text-sm text-ink">Drop one or more reports, invoices, study notes, contracts, or scanned records, or</p>
          <button
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="btn btn-primary"
          >
            {uploading ? "Uploading files…" : "Upload Documents"}
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            disabled={uploading}
            accept={ACCEPT}
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
          <p className="font-mono text-2xs text-ink-faint">
            PDF · PNG · JPG · TXT · DOCX · CSV · PY — max 25 MB · stays on this
            appliance
          </p>
          {notice && (
            <p role="status" className="mt-1 rounded-[3px] border border-signal/30 bg-signal/[0.06] px-3 py-1.5 font-mono text-2xs text-signal">
              {notice}
            </p>
          )}
          {!!uploadResults.length && <ul aria-live="polite" className="mt-3 max-h-52 w-full max-w-xl space-y-1 overflow-auto text-left text-xs">{uploadResults.map((item, index) => <li key={index} className="rounded border border-line bg-surface px-3 py-2"><span className="break-all font-medium">{item.name}</span><span className={`ml-2 ${item.status === "failed" ? "text-danger" : "text-ink-muted"}`}>{item.status}{item.error ? `: ${item.error}` : ""}</span></li>)}</ul>}
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

      {source === "unavailable" && <p role="alert" className="mb-3 text-sm text-danger">Backend unavailable. Connect the local service to load documents.</p>}
      <BatchAnalysisPanel selectedIds={selectedIds} profile={profile} mode={analysisMode} onStarted={() => setSelectedIds([])} />
      {source === "live" && docs.length === 0 && <p className="mb-3 text-sm text-ink-muted">No documents uploaded yet. Upload a file to get started.</p>}
      {/* Table */}
      <Panel>
        <PanelHeader
          title="Vault Contents"
          sub={`${docs.length} documents · stored locally · uploaded documents`}
          icon={<FileText className="h-4 w-4" />}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line font-mono text-2xs uppercase tracking-wider text-ink-faint">
                <th className="px-3 py-2"><input type="checkbox" aria-label="Select all documents for batch analysis" checked={docs.length > 0 && docs.every((doc) => selectedIds.includes(doc.id))} onChange={(event) => setSelectedIds(event.target.checked ? docs.map((doc) => doc.id) : [])} /></th>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Classification</th>
                <th className="px-3 py-2 font-medium">Pages</th>
                <th className="px-3 py-2 font-medium">Processing</th>
                <th className="px-3 py-2 font-medium">Access</th>
                <th className="px-3 py-2 font-medium">Last Processed</th>
                <th className="px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {docs.map((d) => (
                <tr key={d.id} className="hover:bg-surface-raised">
                  <td className="px-3 py-2.5"><input type="checkbox" aria-label={`Select ${d.name} for batch analysis`} checked={selectedIds.includes(d.id)} onChange={(event) => setSelectedIds((ids) => event.target.checked ? [...ids, d.id] : ids.filter((id) => id !== d.id))} /></td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-ink-faint" />
                      <button type="button" onClick={() => setPreviewDocument(d)} className="text-left text-ink hover:text-signal hover:underline" aria-label={`Open ${d.name}`}>{d.name}</button>
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
                                : "Extract dates, amounts, contacts, owners, reference IDs, and measurements with exact source excerpts.";
                            const result = await api.analyzeDocument(
                              d.id,
                              title,
                              description,
                              profile,
                              analysisMode,
                            );
                            const processedDocument = result.document;
                            if (processedDocument) {
                              setDocs((list) => list.map((item) => item.id === d.id
                                ? {
                                    ...item,
                                    pages: processedDocument.pages ?? item.pages,
                                    ocr: processedDocument.status === "analyzed" ? "done"
                                      : processedDocument.status === "needs_ocr" || processedDocument.status === "unreadable"
                                        ? "error" : "pending",
                                    lastProcessed: new Date().toLocaleTimeString("en-GB", { hour12: false }),
                                  }
                                : item));
                            }
                            const outcome = analysisMode === "summary"
                              ? "summary generated"
                              : analysisMode === "extract_fields"
                                ? `${result.run.findings.length} field(s) extracted`
                                : `${result.run.findings.length} risk finding(s) recorded`;
                            setNotice(
                              `Analysis finished: ${outcome}. `
                              + (processedDocument?.ocr_pages
                                ? `Local OCR processed ${processedDocument.ocr_pages} page(s). `
                                : "Source citations include page and text locations. ")
                              + `Run #${result.run.run.id} is in Agent Runs.`,
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
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-3 whitespace-nowrap">
                      <button type="button" onClick={() => setPreviewDocument(d)} className="inline-flex items-center gap-1 text-signal hover:underline" aria-label={`Preview ${d.name}`}>
                        <Eye className="h-3.5 w-3.5" /> Open
                      </button>
                      <button type="button" onClick={() => setDeleteDocument(d)} className="inline-flex items-center gap-1 text-danger hover:underline" aria-label={`Delete ${d.name}`}>
                        <Trash2 className="h-3.5 w-3.5" /> Delete
                      </button>
                    </div>
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
      {previewDocument && <DocumentPreviewDialog key={previewDocument.id} document={previewDocument} onClose={() => setPreviewDocument(null)} />}
      {deleteDocument && <DocumentDeleteDialog key={deleteDocument.id} document={deleteDocument} onClose={() => setDeleteDocument(null)} onDeleted={(id) => {
        setLocallyChanged(true);
        setSelectedIds((ids) => ids.filter((item) => item !== id));
        setDocs((list) => list.filter((item) => item.id !== id));
        setNotice(`${deleteDocument.name} deleted from the Vault. Analysis history and reports are retained.`);
      }} />}
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
