"""Knowledge agent - retrieves supporting context from the RAG knowledge base.

Queries the deterministic in-memory vector index for each detected equipment tag
and stores the retrieved chunks for the reasoning agent.
"""
from __future__ import annotations

from ..rag.pipeline import KnowledgeBase
from ..services import knowledge as knowledge_service
from ..services.document_analysis import PAGE_BREAK
from .base import BaseAgent, RunContext


class KnowledgeAgent(BaseAgent):
    name = "knowledge_agent"

    def run(self, ctx: RunContext) -> RunContext:
        uploaded = ctx.artifacts.get("document")
        if uploaded:
            # Index the uploaded text in a throwaway per-run index and retrieve
            # the passages most relevant to the task.
            doc_kb = KnowledgeBase()
            document_text = ctx.artifacts.get("document_text", "")
            if not document_text.strip():
                ctx.artifacts["retrieved"] = []
                ctx.add_step(
                    self.name,
                    "No text to index",
                    status="skipped",
                    detail=ctx.artifacts.get("document_note", "No text was extracted from this file."),
                )
                return ctx
            pages = document_text.split(PAGE_BREAK)
            chunks = sum(doc_kb.add(page, source=uploaded["filename"], page=n)
                         for n, page in enumerate(pages, start=1))
            hits = [h for h in doc_kb.search(ctx.task_text, top_k=4) if h["score"] > 0]
            ctx.artifacts["retrieved"] = hits
            ctx.add_step(self.name, "Knowledge retrieved",
                         detail=f"Indexed {chunks} chunk(s) of {uploaded['filename']} locally; "
                                f"{len(hits)} relevant to the task.")
            return ctx

        kb = knowledge_service.get_kb()
        queries = ["corrosion P-101 outlet wall thickness",
                   "control valve V-204 actuator packing",
                   "HX-301 fouling factor"]
        retrieved = []
        for q in queries:
            hits = kb.search(q, top_k=2)
            retrieved.extend(hits)
        ctx.artifacts["retrieved"] = retrieved
        ctx.add_step(self.name, "Knowledge retrieved",
                     detail=f"Retrieved {len(retrieved)} chunks across "
                            f"{len(queries)} equipment queries from the local vector DB.")
        return ctx
