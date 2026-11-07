"use client";
import { useRef, useState } from "react";
import { Panel, PanelHeader, PageTitle, SourceChip } from "@/components/ui";
import { EvidenceCard } from "@/components/viz/Findings";
import { api, type KnowledgeSearchResult, type SourceReference } from "@/lib/api";
import { EvidencePreviewDialog } from "@/components/vault/EvidencePreviewDialog";
import { useLive } from "@/lib/live";
export default function KnowledgePage() {
  const { data: catalog, source, error: catalogError } = useLive(api.knowledge, null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reference, setReference] = useState<SourceReference | null>(null);
  const requestId = useRef(0);
  async function search() {
    const id = ++requestId.current;
    setResults([]); setError(null); setSearched(false);
    if (!query.trim()) { setError("Enter a search query."); return; }
    setBusy(true);
    try {
      const response = await api.searchKnowledge(query.trim().slice(0, 500));
      if (id === requestId.current) { setResults(response.results); setSearched(true); }
    } catch (err) { if (id === requestId.current) setError(err instanceof Error ? err.message : "Search unavailable"); }
    finally { if (id === requestId.current) setBusy(false); }
  }
  return <div><PageTitle eyebrow="Local document retrieval" title="Knowledge Base"><SourceChip source={source} /></PageTitle>
    <p className="mb-3 text-sm text-ink-muted">Search text extracted from your stored documents. The local index is rebuilt when files change.</p>
    {catalogError && <p role="alert" className="mb-3 text-danger">Index unavailable: {catalogError}</p>}
    <div className="grid gap-3 lg:grid-cols-[280px_1fr]"><Panel><PanelHeader title="Indexed sources" sub={catalog ? `${catalog.total_chunks} chunks / ${catalog.backend.embedding_backend}` : "Connecting"} /><ul className="divide-y divide-line">{catalog?.sources?.map((item: any) => <li key={item.name} className="p-4 text-sm">{item.name}<span className="block text-xs text-ink-muted">{item.chunks} chunks</span></li>)}</ul>{source === "live" && !catalog?.sources?.length && <p className="p-4 text-sm text-ink-muted">Upload a readable document to build the index.</p>}</Panel>
    <Panel><PanelHeader title="Search evidence" /><div className="space-y-3 p-4"><form onSubmit={(e) => { e.preventDefault(); search(); }} className="flex gap-2"><input aria-label="Search query" maxLength={500} value={query} onChange={(e) => setQuery(e.target.value)} className="min-w-0 flex-1 rounded border border-line bg-surface p-2" placeholder="Search your document text" /><button disabled={busy} className="btn btn-primary">{busy ? "Searching..." : "Search"}</button></form>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {results.map((item, i) => <div key={item.id}><EvidenceCard rank={i+1} ev={{ id: item.id, source: item.source, page: item.page, excerpt: item.text, relevance: Math.max(0, Math.min(100, Math.round(item.score * 100))), tags: [] }} />{item.document_id != null && <button className="mt-1 min-h-8 text-xs text-signal underline" onClick={() => setReference({ document_id: item.document_id!, page: item.page, excerpt: Array.from(item.text).slice(0, 2000).join(""), char_start: item.char_start, char_end: item.char_end })}>View highlighted source</button>}</div>)}
    {searched && !results.length && <p className="text-sm text-ink-muted">No matching passages found.</p>}
    </div></Panel></div>
    {reference && <EvidencePreviewDialog reference={reference} onClose={() => setReference(null)} />}
  </div>;
}
