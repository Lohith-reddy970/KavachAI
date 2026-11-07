"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Download, ExternalLink, Loader2, Trash2, X } from "lucide-react";
import { api, type DocumentPreview } from "@/lib/api";
import type { KDocument } from "@/lib/types";

export function DocumentPreviewDialog({ document, onClose }: {
  document: KDocument; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dialog.current?.showModal();
    let active = true;
    api.documentPreview(document.id)
      .then((result) => { if (active) setPreview(result); })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : "Could not open this document."); });
    return () => { active = false; };
  }, [document.id]);

  const url = api.documentContentUrl(document.id);
  return (
    <dialog ref={dialog} onClose={onClose} aria-labelledby={titleId}
      className="m-auto h-[88vh] max-h-[95vh] w-[96vw] max-w-6xl rounded-lg border border-line bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/50">
      <div className="flex h-full flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0 flex-1">
            <p className="eyebrow text-ink-muted">Document preview</p>
            <h2 id={titleId} className="break-all text-base font-semibold">{document.name}</h2>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            {preview && preview.kind !== "text" && (
              <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-signal hover:underline">
                <ExternalLink className="h-3.5 w-3.5" /> Open in new tab
              </a>
            )}
            <a href={api.documentContentUrl(document.id, true)} className="btn inline-flex items-center gap-1">
              <Download className="h-3.5 w-3.5" /> Download original
            </a>
            <button type="button" autoFocus onClick={() => dialog.current?.close()} aria-label="Close document preview" className="rounded p-2 hover:bg-surface-inset">
              <X className="h-5 w-5" />
            </button>
          </div>
        </header>
        {!preview && !error && <p role="status" className="flex items-center gap-2 p-5 text-sm"><Loader2 className="h-4 w-4 animate-spin" /> Opening document...</p>}
        {error && <p role="alert" className="p-5 text-sm text-danger">{error}</p>}
        {preview && !error && (
          <div className="min-h-0 flex-1 overflow-auto bg-surface-inset">
            {preview.kind === "pdf" && <iframe src={url} title={`PDF preview: ${document.name}`} className="h-full min-h-[400px] w-full border-0" />}
            {preview.kind === "image" && (
              <div className="grid min-h-full place-items-center p-4">
                {/* Native image loading preserves the locally stored original. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt={document.name} className="max-w-full object-contain" onError={() => setError("The image could not be displayed. Try downloading the original file.")} />
              </div>
            )}
            {preview.kind === "text" && (
              <div className="p-5">
                {document.type === "DOCX" && <p className="mb-4 text-xs text-ink-muted">Text preview includes paragraphs and tables. Download the original to see its formatting and embedded images.</p>}
                {preview.note && <p role="status" className="mb-4 text-sm text-ink-muted">{preview.note}</p>}
                <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{preview.text}</pre>
                {preview.truncated && <p className="mt-4 text-xs text-ink-muted">Preview limited to the first 200,000 characters. Download the original for the full document.</p>}
              </div>
            )}
          </div>
        )}
      </div>
    </dialog>
  );
}

export function DocumentDeleteDialog({ document, onClose, onDeleted }: {
  document: KDocument; onClose: () => void; onDeleted: (id: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);

  async function remove() {
    setBusy(true); setError(null);
    try {
      await api.deleteDocument(document.id);
      onDeleted(document.id);
      dialog.current?.close();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this document.");
      setBusy(false);
    }
  }

  return (
    <dialog ref={dialog} onClose={onClose} onCancel={(event) => { if (busy) event.preventDefault(); }} aria-labelledby={titleId}
      className="m-auto w-[94vw] max-w-lg rounded-lg border border-line bg-surface p-6 text-ink shadow-2xl backdrop:bg-black/50">
      <h2 id={titleId} className="text-lg font-semibold">Delete document?</h2>
      <p className="mt-3 break-all text-sm font-medium">{document.name}</p>
      <p className="mt-3 text-sm text-ink-muted">This permanently removes the uploaded source file from the Vault and future knowledge searches. Existing analysis history and generated reports are retained.</p>
      {error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}
      <div className="mt-6 flex justify-end gap-3">
        <button type="button" autoFocus disabled={busy} onClick={() => dialog.current?.close()} className="btn disabled:opacity-50">Cancel</button>
        <button type="button" disabled={busy} onClick={remove} className="btn inline-flex items-center gap-2 border-danger bg-danger text-white disabled:opacity-50">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
          {busy ? "Deleting..." : "Delete permanently"}
        </button>
      </div>
    </dialog>
  );
}
