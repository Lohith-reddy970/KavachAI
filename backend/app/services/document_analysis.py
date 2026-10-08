"""Local, deterministic analysis of an uploaded document.

Used when a run targets an uploaded file. Risk findings are *extractive* -
sentences that match the selected profile's risk vocabulary - so each one quotes
source text that can be re-checked by the verification agent. Field extraction
is also literal; summaries are handled by the reasoning agent.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..domains.profiles import get_profile

#: Separates pages in extracted text so a sentence can be traced to its page.
PAGE_BREAK = "\f"
MAX_FINDINGS = 8
MAX_EXCERPT_CHARS = 400

_SEVERITY_ORDER = ("high", "medium", "low")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_TAG_RE = re.compile(r"\b[A-Z]{1,4}-\d{2,4}[A-Z]?\b")
_DATE_RE = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"
)
_MEASUREMENT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:mm|cm|km|m|kg|g|mg|bar|psi|kpa|mpa|°c|%|"
    r"days?|hours?|years?)(?=\s|[,.;:)]|$)",
    re.IGNORECASE,
)
_SPACE_RE = re.compile(r"\s+")


def extract_text(path: str) -> tuple[str, str]:
    """Return ``(text, note)`` for a stored document; never raises.

    The format comes from the file extension: seeded sample documents store a
    category ("report", "manual") in ``doc_type``, not a file type. ``note`` is
    empty on success, otherwise it says why no text is available (unsupported
    type, optional library missing, unreadable file).
    """
    source = Path(path)
    if not source.is_file():
        return "", "file is missing on disk"
    doc_type = source.suffix.lstrip(".").lower()
    try:
        if doc_type in {"txt", "csv", "py"}:
            return source.read_text(encoding="utf-8", errors="replace"), ""
        if doc_type == "docx":
            try:
                from docx import Document  # type: ignore
            except ImportError:
                return "", "DOCX text extraction needs the optional python-docx package"
            return "\n".join(p.text for p in Document(str(source)).paragraphs), ""
        if doc_type == "pdf":
            try:
                from pypdf import PdfReader  # type: ignore
            except ImportError:
                return "", "PDF text extraction needs the optional pypdf package"
            pages = [page.extract_text() or "" for page in PdfReader(str(source)).pages]
            return PAGE_BREAK.join(pages), ""
    except Exception as exc:  # noqa: BLE001 - a corrupt upload must not 500 the run
        return "", f"could not read {doc_type} file ({type(exc).__name__})"
    return "", (f"no text extractor for .{doc_type} files; OCR is not enabled. "
                 "Use Summary for an image description.")


def _normalize(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip().lower()


def _signals(sentence: str, profile_id: str) -> tuple[str, list[str]]:
    """Return (severity, matched stems) for a sentence; severity '' if no match."""
    low = sentence.lower()
    lexicon = get_profile(profile_id).risk_terms
    hits: dict[str, list[str]] = {}
    for severity, stems in lexicon.items():
        found = [s for s in stems if re.search(rf"\b{re.escape(s)}", low)]
        if found:
            hits[severity] = found
    for severity in _SEVERITY_ORDER:
        if severity in hits:
            return severity, [s for sev in _SEVERITY_ORDER for s in hits.get(sev, [])]
    return "", []


def find_findings(text: str, source: str, profile_id: str = "general") -> list[dict]:
    """Extract findings using the selected profile's risk terms."""
    candidates: list[tuple[int, int, dict]] = []
    order = 0
    for page_no, page in enumerate(text.split(PAGE_BREAK), start=1):
        for raw in _SENTENCE_RE.split(page):
            sentence = _SPACE_RE.sub(" ", raw).strip()
            if len(sentence) < 25:
                continue
            severity, stems = _signals(sentence, profile_id)
            if not severity:
                continue
            excerpt = sentence[:MAX_EXCERPT_CHARS]
            # Lexical match strength, not a model probability.
            confidence = float(min(95, 60 + 10 * len(stems)))
            tags = sorted(set(_TAG_RE.findall(sentence)))
            title = excerpt if len(excerpt) <= 90 else excerpt[:87].rstrip() + "..."
            candidates.append((_SEVERITY_ORDER.index(severity), order, {
                "title": title,
                "description": f"Matched risk terms: {', '.join(stems)}. {excerpt}",
                "severity": severity,
                "confidence": confidence,
                "equipment_id": ", ".join(tags),
                "needs_review": 0,
                "evidence": [{"source": source, "page": page_no, "excerpt": excerpt,
                              "confidence": confidence}],
            }))
            order += 1
    candidates.sort(key=lambda c: (c[0], c[1]))
    return [c[2] for c in candidates[:MAX_FINDINGS]]


def extract_fields(text: str, source: str) -> list[dict]:
    """Extract literal dates, equipment identifiers, and measurements with citations."""
    patterns = (
        ("equipment identifier", _TAG_RE),
        ("date", _DATE_RE),
        ("measurement", _MEASUREMENT_RE),
    )
    findings: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for page_no, page in enumerate(text.split(PAGE_BREAK), start=1):
        for raw in _SENTENCE_RE.split(page):
            sentence = _SPACE_RE.sub(" ", raw).strip()
            if not sentence:
                continue
            for field_name, pattern in patterns:
                for match in pattern.finditer(sentence):
                    value = match.group(0)
                    key = (field_name, value.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    if len(sentence) <= MAX_EXCERPT_CHARS:
                        excerpt = sentence
                    else:
                        start = max(0, min(match.start() - 120,
                                           len(sentence) - MAX_EXCERPT_CHARS))
                        excerpt = sentence[start:start + MAX_EXCERPT_CHARS]
                    findings.append({
                        "title": f"Extracted {field_name}: {value}",
                        "description": f"Literal {field_name} extracted from the source text.",
                        "severity": "info",
                        "confidence": 100.0,
                        "equipment_id": value if field_name == "equipment identifier" else "",
                        "needs_review": 0,
                        "evidence": [{
                            "source": source,
                            "page": page_no,
                            "excerpt": excerpt,
                            "confidence": 100.0,
                        }],
                    })
                    if len(findings) >= MAX_FINDINGS:
                        return findings
    return findings


def verify_findings(findings: list[dict], text: str) -> dict:
    """Re-check every cited excerpt against the document text."""
    haystack = _normalize(text.replace(PAGE_BREAK, " "))
    total = confirmed = backed = 0
    unsupported: list[str] = []
    for f in findings:
        evidence = f.get("evidence") or []
        ok = [bool(e.get("excerpt")) and _normalize(e["excerpt"]) in haystack for e in evidence]
        total += len(ok)
        confirmed += sum(ok)
        if ok and all(ok):
            backed += 1
        else:
            unsupported.append(f.get("title", ""))
    score = round(100.0 * confirmed / total, 1) if total else 0.0
    return {"score": score, "evidence_backed": f"{backed}/{len(findings)}",
            "total_evidence_citations": total, "findings_backed": backed,
            "unsupported": unsupported}
