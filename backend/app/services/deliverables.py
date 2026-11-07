"""Deliverable generation service for KAVACH AI.

Always writes a .txt and a .md report. Additionally writes .docx (python-docx),
.xlsx (openpyxl) and .pdf (reportlab or fpdf2) ONLY when the corresponding
library is importable. All optional imports are guarded; failure degrades
gracefully to the always-available formats.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import textwrap

from .. import config
from ..domains.profiles import ANALYSIS_MODES, get_profile

# --- Optional deps (guarded) --------------------------------------------------
try:
    import docx  # type: ignore
    _DOCX = True
except Exception:  # noqa: BLE001
    _DOCX = False

try:
    import openpyxl  # type: ignore
    _XLSX = True
except Exception:  # noqa: BLE001
    _XLSX = False

_PDF_LIB = None
try:
    from reportlab.lib.pagesizes import letter  # type: ignore
    from reportlab.pdfgen import canvas as _rl_canvas  # type: ignore
    _PDF_LIB = "reportlab"
except Exception:  # noqa: BLE001
    try:
        from fpdf import FPDF  # type: ignore
        _PDF_LIB = "fpdf2"
    except Exception:  # noqa: BLE001
        _PDF_LIB = None


def optional_formats() -> dict[str, Any]:
    return {"docx": _DOCX, "xlsx": _XLSX, "pdf": bool(_PDF_LIB), "pdf_lib": _PDF_LIB}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _subject(ctx) -> tuple[str, str]:
    uploaded = ctx.artifacts.get("document")
    if not uploaded:
        raise ValueError("Reports require a source document.")
    return (f"Source document: {uploaded['filename']}",
            "LOCAL ANALYSIS OUTPUT - REVIEW BEFORE OPERATIONAL USE")


def _analysis_labels(ctx) -> tuple[str, str]:
    profile_id = ctx.artifacts.get("analysis_profile", "general")
    profile = get_profile(profile_id)
    mode_id = ctx.artifacts.get("analysis_mode", "risk_review")
    mode = next((item for item in ANALYSIS_MODES if item["id"] == mode_id), None)
    return profile.name, mode["name"] if mode else mode_id.replace("_", " ").title()


def _evidence_location(ev: dict) -> str:
    """Format a page-local text span and optional normalized OCR box."""
    parts: list[str] = []
    if ev.get("page") is not None:
        parts.append(f"p.{ev['page']}")
    location = ev.get("location") or {}
    start, end = location.get("char_start"), location.get("char_end")
    if isinstance(start, int) and isinstance(end, int):
        parts.append(f"chars {start}-{end}")
    bbox = location.get("bbox") or {}
    if bbox:
        parts.append(
            "box x={:.1f}%, y={:.1f}%, w={:.1f}%, h={:.1f}%".format(
                100 * bbox.get("x", 0), 100 * bbox.get("y", 0),
                100 * bbox.get("width", 0), 100 * bbox.get("height", 0),
            )
        )
    return "; ".join(parts)


def _report_lines(ctx) -> list[str]:
    v = ctx.artifacts.get("verification", {})
    subject, disclaimer = _subject(ctx)
    profile_name, mode_name = _analysis_labels(ctx)
    summary = ctx.artifacts.get("reasoning_analysis", {}).get("text", "")
    is_summary = ctx.artifacts.get("analysis_mode") == "summary"
    vision = ctx.artifacts.get("vision_result") or {}
    show_vision = bool(vision.get("text")) and not (is_summary and summary == vision["text"])
    section_offset = int(is_summary and bool(summary)) + int(show_vision)
    lines = [
        f"{config.APP_NAME} - Document Analysis Report",
        subject,
        f"Generated: {_now()} | Mode: {config.KAVACH_MODE}",
        f"Run ID: {ctx.artifacts.get('run_id')}",
        f"Profile: {profile_name} | Analysis: {mode_name}",
        "",
        disclaimer,
        "=" * 64,
        "",
        "1. EXECUTIVE SUMMARY",
        ("   Verification score: not applicable to summary mode"
         if is_summary else "   Verification score: not applicable (no source-cited findings)"
         if ctx.verification_score is None else f"   Verification score: {ctx.verification_score}%"),
        ("   Evidence-backed: not applicable" if is_summary
         else f"   Evidence-backed: {ctx.evidence_backed}"),
        f"   Model routing: {ctx.routing.get('model')} ({ctx.routing.get('task_type')})",
    ]
    if is_summary and summary:
        lines.extend(["", "2. DOCUMENT SUMMARY", summary])
    if show_vision:
        number = 2 + int(is_summary and bool(summary))
        lines.extend(["", f"{number}. IMAGE INSPECTION", vision["text"],
                      f"Model: {vision['model']} | Provider: {vision['provider']}",
                      "Advisory visual observations; OCR fields and source-text verification are separate."])
    findings_section = 2 + section_offset
    lines.extend(["", f"{findings_section}. FINDINGS"])
    for i, f in enumerate(ctx.findings, start=1):
        flag = " [NEEDS HUMAN REVIEW]" if f.get("needs_review") else ""
        lines.append(f"   {i}. [{f['severity'].upper()}] {f['title']}{flag}")
        lines.append(f"      Reference / topic: {f['equipment_id'] or 'not specified'} | Confidence: {f['confidence']}%")
        lines.append(f"      {f['description']}")
        for ev in f.get("evidence", []):
            provenance = f"; extraction={ev.get('extraction_method')}" if ev.get("extraction_method") else ""
            if ev.get("ocr_confidence") is not None:
                provenance += f"; OCR confidence={ev['ocr_confidence']}%"
            lines.append(f"      - Evidence: {ev['source']} ({_evidence_location(ev)}) "
                         f"[{ev.get('confidence')}%]{provenance}")
            lines.append(f"        \"{ev.get('excerpt', '')}\"")
        lines.append("")
    if is_summary:
        lines.extend([
            f"{findings_section + 1}. VERIFICATION",
            "   Not applicable: summary mode does not create findings to verify.",
            "",
        ])
    else:
        lines.extend([
            f"{findings_section + 1}. VERIFICATION",
            f"   Score: {str(v['score']) + '%' if v.get('score') is not None else 'not applicable'} | Evidence-backed: {v.get('evidence_backed')}",
            *( ["   Visual observations have not been independently verified."] if ctx.artifacts.get("vision_result") else [] ),
            f"   Findings flagged for review: {', '.join(v.get('needs_human_review', [])) or 'none'}",
            "",
        ])
    lines.append(f"{findings_section + 2}. PIPELINE TRACE")
    for s in ctx.steps:
        lines.append(f"   - [{s.agent}] {s.message}")
    return lines


def _md_report(ctx) -> str:
    v = ctx.artifacts.get("verification", {})
    subject, disclaimer = _subject(ctx)
    profile_name, mode_name = _analysis_labels(ctx)
    summary = ctx.artifacts.get("reasoning_analysis", {}).get("text", "")
    is_summary = ctx.artifacts.get("analysis_mode") == "summary"
    vision = ctx.artifacts.get("vision_result") or {}
    md = [
        f"# {config.APP_NAME} - Document Analysis Report",
        "",
        f"**{subject}**  ",
        f"**Generated:** {_now()}  ",
        f"**Mode:** `{config.KAVACH_MODE}`  |  **Run ID:** {ctx.artifacts.get('run_id')}",
        f"**Profile:** {profile_name}  |  **Analysis:** {mode_name}",
        "",
        f"> {disclaimer}",
        "",
        "## Executive Summary",
        "",
        ("- **Verification score:** Not applicable to summary mode"
         if is_summary else "- **Verification score:** Not applicable (no source-cited findings)"
         if ctx.verification_score is None else f"- **Verification score:** {ctx.verification_score}%"),
        ("- **Evidence-backed:** Not applicable"
         if is_summary else f"- **Evidence-backed:** {ctx.evidence_backed}"),
        f"- **Model routing:** {ctx.routing.get('model')} ({ctx.routing.get('task_type')})",
        "",
    ]
    if is_summary and summary:
        md.extend(["## Document Summary", "", summary, ""])
    if vision.get("text") and not (is_summary and summary == vision["text"]):
        md.extend(["## Image Inspection", "", vision["text"], "",
                   f"Model: {vision['model']} / Provider: {vision['provider']}", "",
                   "Advisory visual observations. OCR fields and source-text verification are separate.", ""])
    md.extend(["## Findings", ""])
    for i, f in enumerate(ctx.findings, start=1):
        flag = " _(needs human review)_" if f.get("needs_review") else ""
        md.append(f"### {i}. {f['title']}{flag}")
        md.append("")
        md.append(f"- **Severity:** {f['severity']}")
        md.append(f"- **Reference / topic:** {f['equipment_id'] or 'not specified'}")
        md.append(f"- **Confidence:** {f['confidence']}%")
        md.append(f"- {f['description']}")
        md.append("")
        md.append("| Source | Page and location | Extraction | OCR confidence | Confidence | Excerpt |")
        md.append("|---|---|---|---:|---:|---|")
        for ev in f.get("evidence", []):
            excerpt = ev.get("excerpt", "").replace("|", "/").replace("\n", " ")
            source = ev.get("source", "").replace("|", "/")
            method = ev.get("extraction_method") or "text"
            ocr_confidence = (f"{ev['ocr_confidence']}%"
                              if ev.get("ocr_confidence") is not None else "—")
            md.append(
                f"| {source} | {_evidence_location(ev)} | {method} | {ocr_confidence} | "
                f"{ev.get('confidence')}% | {excerpt} |"
            )
        md.append("")
    if is_summary:
        md.extend([
            "## Verification",
            "",
            "Not applicable: summary mode does not create findings to verify.",
            "",
        ])
    else:
        md.extend([
            "## Verification",
            "",
            f"- Score: **{str(v['score']) + '%' if v.get('score') is not None else 'not applicable'}**",
            f"- Evidence-backed: **{v.get('evidence_backed')}**",
            f"- Flagged for review: {', '.join(v.get('needs_human_review', [])) or 'none'}",
            "",
        ])
    md.extend(["## Pipeline Trace", ""])
    for s in ctx.steps:
        md.append(f"1. **{s.agent}** - {s.message}")
    return "\n".join(md)


def generate_all(ctx) -> list[dict]:
    """Write all deliverables for the run; return list of metadata dicts."""
    config.ensure_dirs()
    run_id = ctx.artifacts.get("run_id", 0)
    base = f"kavach_report_run{run_id}"
    out_dir = config.GENERATED_DIR
    produced: list[dict] = []

    def record(path: Path, fmt: str, name: str) -> None:
        produced.append({
            "name": name,
            "filename": path.name,
            "path": str(path),
            "fmt": fmt,
            "size_bytes": path.stat().st_size if path.exists() else 0,
        })

    lines = _report_lines(ctx)

    # Always: .txt
    txt_path = out_dir / f"{base}.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    record(txt_path, "txt", "Document Analysis Report (Text)")

    # Always: .md
    md_path = out_dir / f"{base}.md"
    md_path.write_text(_md_report(ctx), encoding="utf-8")
    record(md_path, "md", "Document Analysis Report (Markdown)")

    # Optional: .docx
    if _DOCX:
        try:
            doc = docx.Document()
            doc.add_heading(f"{config.APP_NAME} - Document Analysis Report", level=0)
            for line in _subject(ctx):
                doc.add_paragraph(line)
            profile_name, mode_name = _analysis_labels(ctx)
            doc.add_paragraph(f"Profile: {profile_name} | Analysis: {mode_name}")
            summary = ctx.artifacts.get("reasoning_analysis", {}).get("text", "")
            if ctx.artifacts.get("analysis_mode") == "summary" and summary:
                doc.add_heading("Document Summary", level=1)
                doc.add_paragraph(summary)
            vision = ctx.artifacts.get("vision_result") or {}
            if vision.get("text") and not (ctx.artifacts.get("analysis_mode") == "summary" and summary == vision["text"]):
                doc.add_heading("Image Inspection", level=1)
                doc.add_paragraph(vision["text"])
                doc.add_paragraph("Advisory visual observations; OCR fields are verified separately.")
            doc.add_heading("Findings", level=1)
            for f in ctx.findings:
                doc.add_heading(f["title"], level=2)
                doc.add_paragraph(
                    f"Severity: {f['severity']} | Reference / topic: {f['equipment_id']} | "
                    f"Confidence: {f['confidence']}%")
                doc.add_paragraph(f["description"])
                for ev in f.get("evidence", []):
                    provenance = (f"; OCR confidence {ev['ocr_confidence']}%"
                                  if ev.get("ocr_confidence") is not None else "")
                    doc.add_paragraph(
                        f"Evidence: {ev['source']} ({_evidence_location(ev)}) - "
                        f"{ev.get('excerpt', '')}{provenance}",
                        style="List Bullet")
            docx_path = out_dir / f"{base}.docx"
            doc.save(str(docx_path))
            record(docx_path, "docx", "Document Analysis Report (Word)")
        except Exception:  # noqa: BLE001
            pass

    # Optional: .xlsx (findings matrix)
    if _XLSX:
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Findings"
            ws.append(["#", "Title", "Severity", "Reference / topic", "Confidence%",
                       "Needs Review", "Evidence Count"])
            for i, f in enumerate(ctx.findings, start=1):
                ws.append([i, f["title"], f["severity"], f["equipment_id"],
                           f["confidence"], bool(f["needs_review"]),
                           len(f.get("evidence", []))])
            vision = ctx.artifacts.get("vision_result") or {}
            if vision.get("text"):
                visual = wb.create_sheet("Image Inspection")
                visual.append(["Source", vision["source"]])
                visual.append(["Model", vision["model"]])
                visual.append(["Provider", vision["provider"]])
                visual.append(["Status", "Advisory visual observations; not verified OCR fields"])
                visual.append(["Observations", vision["text"]])
                visual.cell(row=5, column=2).data_type = "s"
            xlsx_path = out_dir / f"{base}.xlsx"
            wb.save(str(xlsx_path))
            record(xlsx_path, "xlsx", "Document Fields and Findings (Excel)")
        except Exception:  # noqa: BLE001
            pass

    # Optional: .pdf
    if _PDF_LIB == "reportlab":
        try:
            pdf_path = out_dir / f"{base}.pdf"
            c = _rl_canvas.Canvas(str(pdf_path), pagesize=letter)
            c.setFont("Helvetica", 9)
            width, height = letter
            y = height - 50
            for line in (segment for line in lines for paragraph in line.splitlines() or [""]
                         for segment in textwrap.wrap(paragraph, width=100) or [""]):
                if y < 50:
                    c.showPage()
                    c.setFont("Helvetica", 9)
                    y = height - 50
                c.drawString(40, y, line)
                y -= 14
            c.save()
            record(pdf_path, "pdf", "Document Analysis Report (PDF)")
        except Exception:  # noqa: BLE001
            pass
    elif _PDF_LIB == "fpdf2":
        try:
            pdf_path = out_dir / f"{base}.pdf"
            pdf = FPDF()
            pdf.set_margins(15, 15, 15)
            pdf.add_page()
            pdf.set_font("Helvetica", size=9)
            for line in lines:
                safe = line.encode("latin-1", "replace").decode("latin-1") or " "
                pdf.multi_cell(0, 5, safe, new_x="LMARGIN", new_y="NEXT")
            pdf.output(str(pdf_path))
            record(pdf_path, "pdf", "Document Analysis Report (PDF)")
        except Exception:  # noqa: BLE001
            pass

    return produced
