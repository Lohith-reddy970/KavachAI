"use client";

import Link from "next/link";
import { Fragment, useRef, useState } from "react";
import { MessageSquare, Send } from "lucide-react";
import { api, type ChatResponse, type SourceReference } from "@/lib/api";
import { useLive, fetchDocuments } from "@/lib/live";
import { Panel, PanelHeader, PageTitle, SourceChip } from "@/components/ui";
import { EvidencePreviewDialog } from "@/components/vault/EvidencePreviewDialog";

type Turn = { question: string; response: ChatResponse; scope: string[] };

export default function DocumentChatPage() {
  const { data: documents, source, error: documentsError } = useLive(fetchDocuments, []);
  const [selected, setSelected] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [reference, setReference] = useState<SourceReference | null>(null);
  const lock = useRef(false);
  const result = useRef<HTMLDivElement>(null);

  function changeScope(ids: string[]) {
    setSelected(ids); setTurns([]); setError(null);
  }

  async function ask() {
    if (lock.current || !question.trim() || !selected.length) return;
    lock.current = true; setBusy(true); setError(null);
    const prompt = question.trim(); setPendingQuestion(prompt);
    const history = turns.slice(-4).flatMap((turn) => [
      { role: "user" as const, content: turn.question },
      { role: "assistant" as const, content: turn.response.answer.slice(0, 6000) },
    ]);
    try {
      const response = await api.chat(prompt, selected.map(Number), history);
      setTurns((items) => [...items, { question: prompt, response, scope: documents.filter((doc) => selected.includes(doc.id)).map((doc) => doc.name) }]);
      setQuestion("");
      requestAnimationFrame(() => result.current?.scrollIntoView({ block: "nearest", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }));
    } catch (err) { setError(err instanceof Error ? err.message : "The local model could not answer. Your question is kept so you can retry."); }
    finally { lock.current = false; setBusy(false); setPendingQuestion(""); }
  }

  function answerText(turn: Turn) {
    return turn.response.answer.split(/(\[\d+\])/g).map((part, index) => {
      const number = /^\[(\d+)\]$/.exec(part);
      const citation = number ? turn.response.citations.find((item) => item.number === Number(number[1])) : null;
      return citation ? <button key={index} onClick={() => setReference(citation)} className="mx-0.5 inline-block rounded border border-signal/30 bg-signal/10 px-1.5 py-0.5 text-xs font-semibold text-signal" aria-label={`Open source ${citation.number}: ${citation.source}, page ${citation.page}`}>{part}</button> : <Fragment key={index}>{part}</Fragment>;
    });
  }

  return <div>
    <PageTitle eyebrow="Answers from your selected local documents" title="Document Chat"><SourceChip source={source} /></PageTitle>
    <p className="mb-4 max-w-3xl text-sm leading-relaxed text-ink-muted">Choose up to 20 files and ask a question. Answers use retrieved source passages and your configured local model. Open a citation to inspect the highlighted source. Answers are advisory; citation support does not establish factual correctness.</p>
    <div className="grid items-start gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <Panel><PanelHeader title="Select your sources" sub={`${selected.length} / 20 documents selected`} /><div className="space-y-3 p-4">
        <Link href="/vault" className="inline-block text-xs text-signal hover:underline">Upload documents in the Vault</Link>
        {documentsError && <p role="alert" className="text-xs text-danger">{documentsError}</p>}
        {source === "loading" && <p className="text-xs text-ink-muted">Loading stored documents…</p>}
        {source === "live" && !documents.length && <p className="text-xs text-ink-muted">Upload a readable document to start a conversation.</p>}
        <ul className="max-h-[50vh] space-y-1 overflow-auto">{documents.map((doc) => <li key={doc.id}><label className="flex cursor-pointer items-start gap-2 rounded border border-line p-3 text-xs"><input type="checkbox" disabled={busy || (!selected.includes(doc.id) && selected.length >= 20)} checked={selected.includes(doc.id)} onChange={(event) => changeScope(event.target.checked ? [...selected, doc.id] : selected.filter((id) => id !== doc.id))} className="mt-0.5" /><span className="min-w-0 break-all">{doc.name}<span className="mt-1 block text-ink-muted">{doc.type}</span></span></label></li>)}</ul>
        <p className="text-xs text-ink-muted">Changing sources starts a new conversation. Chat stays in this browser tab and clears on refresh.</p>
      </div></Panel>
      <Panel><PanelHeader title="Ask your documents" icon={<MessageSquare size={17} />} right={<button type="button" disabled={busy || !turns.length} onClick={() => { setTurns([]); setError(null); }} className="text-xs text-signal disabled:opacity-40">New conversation</button>} />
        <div className="space-y-5 p-4 sm:p-5">
          {!turns.length && !busy && <div className="rounded border border-line bg-surface-inset p-5"><h2 className="font-display text-xl font-semibold">Start with a question you can check.</h2><p className="mt-2 text-sm text-ink-muted">For example: “What deadlines are mentioned?”, “Which amounts appear in these invoices?”, or “What does the policy say about renewals?”</p><p className="mt-3 text-xs text-ink-muted">Scanned pages need local OCR. Chat works from extracted text; visual observations are available through document analysis in Workbench.</p></div>}
          <div className="space-y-5" aria-live="polite" aria-busy={busy}>{turns.map((turn, index) => <article key={index} className="space-y-3 border-b border-line pb-5"><div className="rounded border border-line bg-surface-inset p-3"><p className="eyebrow mb-1">Your question</p><p className="whitespace-pre-wrap break-words text-sm">{turn.question}</p></div><div><p className="eyebrow mb-2">{turn.response.status === "cited" ? "Local answer · source cited" : "More source information needed"}</p><div className="whitespace-pre-wrap break-words text-sm leading-relaxed">{answerText(turn)}</div></div>{turn.response.citations.length > 0 && <ul className="space-y-2">{turn.response.citations.map((citation) => <li key={citation.number}><button onClick={() => setReference(citation)} className="w-full rounded border border-line bg-surface-raised p-3 text-left text-xs hover:border-signal"><strong className="text-signal">[{citation.number}] {citation.source} · p.{citation.page}</strong><span className="mt-1 block whitespace-pre-wrap break-words leading-relaxed text-ink-muted">{citation.excerpt}</span><span className="mt-2 block text-signal">View highlighted source</span></button></li>)}</ul>}<p className="break-words font-mono text-2xs text-ink-muted">{turn.response.model ? `${turn.response.model} / ${turn.response.provider}` : "No matching source passages found"} · {turn.scope.join(", ")}</p></article>)}</div>
          {busy && <p role="status" className="rounded border border-line p-3 text-sm text-ink-muted">Reading the selected sources and asking the local model: {pendingQuestion}</p>}
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          <div ref={result} />
          <form onSubmit={(event) => { event.preventDefault(); void ask(); }} className="space-y-3 border-t border-line pt-4"><label className="block"><span className="eyebrow mb-2 block">Your question</span><textarea value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={2000} rows={3} disabled={busy} placeholder={selected.length ? "Ask about the selected documents…" : "Select at least one document to begin…"} className="w-full resize-y rounded border border-line bg-surface p-3 text-sm" /></label><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-ink-muted">{selected.length ? `Answers are limited to ${selected.length} selected document(s).` : "Select a source document first."}</p><button type="submit" disabled={busy || source !== "live" || !selected.length || !question.trim()} className="btn btn-primary"><Send size={14} />{busy ? "Generating…" : "Ask documents"}</button></div></form>
        </div>
      </Panel>
    </div>
    {reference && <EvidencePreviewDialog reference={reference} onClose={() => setReference(null)} />}
  </div>;
}
