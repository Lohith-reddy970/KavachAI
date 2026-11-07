"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Download, Loader2, X } from "lucide-react";
import { api, type EvidencePreview, type SourceReference } from "@/lib/api";

export function EvidencePreviewDialog({ evidenceId, reference, onClose }: {
  evidenceId?: number; reference?: SourceReference; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const mark = useRef<HTMLElement>(null);
  const titleId = useId();
  const [data, setData] = useState<EvidencePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    dialog.current?.showModal();
    let alive = true;
    const load = evidenceId != null ? api.evidencePreview(evidenceId) : reference ? api.sourcePassage(reference) : Promise.reject(new Error("No source selected."));
    load.then((result) => { if (alive) setData(result); }).catch((err) => { if (alive) setError(err instanceof Error ? err.message : "The source could not be opened."); });
    return () => { alive = false; };
  }, [evidenceId, reference]);

  useEffect(() => { mark.current?.scrollIntoView({ block: "center" }); }, [data]);
  // Source offsets count Unicode code points, while JavaScript slice counts UTF-16 units.
  const characters = data ? Array.from(data.text) : [];

  return <dialog ref={dialog} onClose={onClose} aria-labelledby={titleId} className="m-auto h-[90vh] max-h-[96vh] w-[96vw] max-w-6xl rounded-lg border border-line bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/50">
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0 flex-1"><p className="eyebrow">Highlighted source evidence</p><h2 id={titleId} className="break-words font-semibold">{data ? `${data.filename} / ${data.page_label}` : "Opening source"}</h2></div>
        {data && <a href={api.documentContentUrl(String(data.document_id), true)} className="btn btn-ghost"><Download size={14} /> Original</a>}
        <button autoFocus onClick={() => dialog.current?.close()} aria-label="Close source evidence" className="rounded p-2 hover:bg-surface-inset"><X size={20} /></button>
      </header>
      {!data && !error && <p role="status" className="flex items-center gap-2 p-5 text-sm"><Loader2 className="h-4 w-4 animate-spin" /> Locating the quoted passage…</p>}
      {error && <p role="alert" className="p-5 text-sm text-danger">{error}</p>}
      {data && <div className={`grid min-h-0 flex-1 overflow-auto ${data.has_image ? "lg:grid-cols-[1.3fr_1fr]" : ""}`}>
        {data.has_image && <div className="overflow-auto bg-surface-inset p-4">
          <p className="mb-3 text-xs text-ink-muted">Original page{data.boxes.length ? " · matching text highlighted" : " · see extracted text for the verified passage"}</p>
          {imageError ? <p role="status" className="text-sm text-ink-muted">The original page could not be rendered. The verified text is available alongside it.</p> : <div className="relative mx-auto w-fit max-w-full">
            {/* The local page endpoint renders the same orientation used for OCR. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={api.sourcePageUrl(data.document_id, data.page)} alt={`${data.filename}, ${data.page_label}`} className="block h-auto max-w-full" onError={() => setImageError(true)} />
            <div aria-hidden="true" className="pointer-events-none absolute inset-0">{data.boxes.map((box, index) => <span key={index} className="absolute border border-signal/80 bg-yellow-400/30" style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%` }} />)}</div>
          </div>}
        </div>}
        <div className="overflow-auto p-5"><h3 className="eyebrow mb-3">Verified passage in extracted text</h3>{data.note && <p className="mb-3 text-xs text-ink-muted">{data.note}</p>}
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{characters.slice(0, data.highlight_start).join("")}<mark ref={mark} className="rounded bg-yellow-200 px-0.5 text-ink">{characters.slice(data.highlight_start, data.highlight_end).join("")}</mark>{characters.slice(data.highlight_end).join("")}</pre>
          {data.truncated && <p className="mt-4 text-xs text-ink-muted">Showing the surrounding text. Download the original for the full document.</p>}
        </div>
      </div>}
    </div>
  </dialog>;
}
