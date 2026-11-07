"""Build and render the project report without changing application dependencies."""
from pathlib import Path
from html import escape
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tmp" / "report-tools"))

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Preformatted, Spacer, Table, TableStyle,
)

SOURCE = ROOT / "docs" / "KAVACH-AI-Project-Report.md"
OUTPUT = ROOT / "output" / "pdf" / "KAVACH-AI-Project-Report.pdf"
QA = ROOT / "tmp" / "report-qa"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)

FONT_DIR = Path("C:/Windows/Fonts")
for name, filename in [("Report", "calibri.ttf"), ("ReportBold", "calibrib.ttf"), ("ReportItalic", "calibrii.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
pdfmetrics.registerFontFamily("Report", normal="Report", bold="ReportBold", italic="ReportItalic", boldItalic="ReportBold")

INK = colors.HexColor("#202923")
MUTED = colors.HexColor("#526056")
GREEN = colors.HexColor("#243B31")
ORANGE = colors.HexColor("#AE4228")
LINE = colors.HexColor("#D9D9D9")
PAPER = colors.HexColor("#F1F3ED")
WIDTH, HEIGHT = A4
MARGIN = 54
CONTENT = WIDTH - MARGIN * 2

STYLES = {
    "body": ParagraphStyle("Body", fontName="Report", fontSize=10.4, leading=14.5, textColor=INK, spaceAfter=8, allowWidows=0, allowOrphans=0, alignment=TA_LEFT),
    "title": ParagraphStyle("Title", fontName="ReportBold", fontSize=32, leading=36, textColor=colors.black, spaceAfter=13),
    "h1": ParagraphStyle("Heading1", fontName="ReportBold", fontSize=23, leading=28, textColor=colors.black, spaceAfter=16, keepWithNext=True),
    "h2": ParagraphStyle("Heading2", fontName="ReportBold", fontSize=13, leading=17, textColor=colors.black, spaceBefore=9, spaceAfter=7, keepWithNext=True),
    "bullet": ParagraphStyle("Bullet", fontName="Report", fontSize=10.4, leading=14.5, textColor=INK, spaceAfter=6, leftIndent=17, bulletIndent=2, allowWidows=0, allowOrphans=0),
    "source": ParagraphStyle("Source", fontName="ReportItalic", fontSize=8, leading=11, textColor=MUTED, spaceBefore=7, spaceAfter=3),
    "ref": ParagraphStyle("Reference", fontName="Report", fontSize=8.3, leading=10.8, textColor=INK, spaceAfter=4, leftIndent=11, firstLineIndent=-11),
    "cell": ParagraphStyle("Cell", fontName="Report", fontSize=9.1, leading=12, textColor=INK),
    "cellHead": ParagraphStyle("CellHead", fontName="ReportBold", fontSize=9.2, leading=12, textColor=colors.white),
    "code": ParagraphStyle("Code", fontName="Courier", fontSize=8.6, leading=12, textColor=INK, backColor=PAPER, borderPadding=9, spaceBefore=5, spaceAfter=12),
    "subtitle": ParagraphStyle("Subtitle", fontName="Report", fontSize=17, leading=22, textColor=colors.black, spaceAfter=12),
    "meta": ParagraphStyle("Metadata", fontName="Report", fontSize=10, leading=15, textColor=MUTED, spaceAfter=25),
}


def inline(text):
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="8.4">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


class Architecture(Flowable):
    def __init__(self):
        super().__init__(); self.width = CONTENT; self.height = 188

    def draw(self):
        c = self.canv
        def box(x, y, w, h, title, lines, dark=False):
            c.setStrokeColor(LINE); c.setLineWidth(.65)
            c.setFillColor(GREEN if dark else PAPER)
            c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
            c.setFillColor(colors.white if dark else INK)
            c.setFont("ReportBold", 11)
            c.drawCentredString(x + w / 2, y + h - 18, title)
            c.setFont("Report", 9)
            for n, line in enumerate(lines):
                c.drawCentredString(x + w / 2, y + h - 33 - n * 11, line)
        def arrow(x, y, end):
            c.setStrokeColor(ORANGE); c.setFillColor(ORANGE); c.setLineWidth(1)
            c.line(x, y, x, end)
            p = c.beginPath(); p.moveTo(x - 3, end + 5); p.lineTo(x, end); p.lineTo(x + 3, end + 5); p.close()
            c.drawPath(p, fill=1, stroke=0)
        box(0, 139, CONTENT, 43, "Browser interface", ["Next.js pages  |  file selection  |  progress  |  results and review"])
        arrow(CONTENT / 2, 139, 122)
        box(0, 78, CONTENT, 44, "FastAPI backend and document services", ["Validation  |  jobs and batches  |  agents  |  retrieval  |  source checks"], True)
        w = (CONTENT - 24) / 3
        for i, (title, lines) in enumerate([
            ("Local storage", ["SQLite records", "Originals and reports"]),
            ("Local retrieval", ["Source passages and vectors", "Selected document context"]),
            ("Local models", ["Ollama or local Transformers", "Reasoning and supported vision"]),
        ]):
            x = i * (w + 12)
            arrow(x + w / 2, 78, 63)
            box(x, 4, w, 59, title, lines)


class ReportDoc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=61, bottomMargin=47, title="KAVACH AI Project Report",
                         author="KAVACH AI project documentation", subject="Website purpose features architecture and operation")
        frame = Frame(MARGIN, 47, CONTENT, HEIGHT - 108, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id="Report", frames=frame, onPage=self.page_header))
        self.heading_pages = []

    def page_header(self, c, doc):
        c.saveState(); c.setFont("ReportBold", 8); c.setFillColor(colors.black)
        c.drawString(MARGIN, HEIGHT - 32, "KAVACH AI")
        c.setFont("Report", 8); c.drawRightString(WIDTH - MARGIN, HEIGHT - 32, "PROJECT REPORT  |  7 NOVEMBER 2026")
        c.setStrokeColor(LINE); c.setLineWidth(.5); c.line(MARGIN, HEIGHT - 41, WIDTH - MARGIN, HEIGHT - 41)
        c.restoreState()

    def afterFlowable(self, item):
        if isinstance(item, Paragraph) and item.style.name in {"Title", "Heading1"}:
            self.heading_pages.append((item.getPlainText(), self.page))


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.saved = []
    def showPage(self):
        self.saved.append(dict(self.__dict__)); self._startPage()
    def save(self):
        count = len(self.saved)
        for state in self.saved:
            self.__dict__.update(state)
            self.saveState(); self.setStrokeColor(LINE); self.setLineWidth(.5)
            self.line(MARGIN, 35, WIDTH - MARGIN, 35)
            self.setFillColor(MUTED); self.setFont("Report", 8)
            self.drawString(MARGIN, 22, "Implementation overview  |  Local document intelligence")
            self.drawRightString(WIDTH - MARGIN, 22, f"{self._pageNumber:02d} / {count:02d}")
            self.restoreState(); super().showPage()
        super().save()


def render_table(rows, chapter):
    cells = [row.strip().strip("|").split("|") for row in rows]
    cells = [[value.strip() for value in row] for row in cells]
    cells = [row for row in cells if not all(re.fullmatch(r"[: -]+", value) for value in row)]
    n = len(cells[0])
    if n == 2:
        ratios = [.27, .73] if chapter == 13 else [.43, .57]
    else:
        ratios = [.23, .36, .41]
    widths = [CONTENT * ratio for ratio in ratios]
    content = [[Paragraph(inline(value), STYLES["cellHead" if i == 0 else "cell"]) for value in row] for i, row in enumerate(cells)]
    table = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F6F3")]),
        ("GRID", (0, 0), (-1, -1), .5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [table, Spacer(1, 11)]


def parse(chapter, chapter_index):
    lines = chapter.strip().splitlines(); items = []; i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line: i += 1; continue
        if line.startswith("# "):
            items.append(Spacer(1, 20)); items.append(Paragraph(inline(line[2:]), STYLES["title"]))
        elif chapter_index == 0 and line == "Website features architecture and operation":
            items.append(Paragraph(line, STYLES["subtitle"]))
        elif chapter_index == 0 and line.startswith("Implementation reviewed"):
            items.append(Paragraph(line, STYLES["meta"]))
        elif line.startswith("## "):
            style = STYLES["h2"] if chapter_index == 0 else STYLES["h1"]
            items.append(Paragraph(inline(line[3:]), style))
        elif line.startswith("### "):
            items.append(Paragraph(inline(line[4:]), STYLES["h2"]))
        elif line == "[[ARCHITECTURE]]":
            items.extend([Architecture(), Spacer(1, 10)])
        elif line.startswith("```"):
            code = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            items.append(Preformatted("\n".join(code), STYLES["code"]))
        elif line.startswith("|"):
            table = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table.append(lines[i]); i += 1
            items.extend(render_table(table, chapter_index)); continue
        elif line.startswith("Source basis"):
            items.append(Paragraph(inline(line), STYLES["source"]))
        elif chapter_index == 13 and re.match(r"^- S\d+ ", line):
            items.append(Paragraph(inline(line[2:]), STYLES["ref"]))
        elif line.startswith("- "):
            items.append(Paragraph(inline(line[2:]), STYLES["bullet"], bulletText="-"))
        elif re.match(r"^\d+\. ", line):
            number, content = line.split(". ", 1)
            items.append(Paragraph(inline(content), STYLES["bullet"], bulletText=number + "."))
        else:
            paragraph = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith(("#", "- ", "|", "```", "[[")):
                i += 1; paragraph.append(lines[i].strip())
            items.append(Paragraph(inline(" ".join(paragraph)), STYLES["body"]))
        i += 1
    return items


chapters = SOURCE.read_text(encoding="utf-8").split("<!-- page -->")
story = []
for index, chapter in enumerate(chapters):
    if index: story.append(PageBreak())
    story.extend(parse(chapter, index))
doc = ReportDoc(OUTPUT)
doc.build(story, canvasmaker=NumberedCanvas)

import pymupdf
from PIL import Image, ImageDraw, ImageFont

# Add destinations after the numbered canvas has materialized its final PDF pages.
with pymupdf.open(OUTPUT) as navigation:
    navigation.set_toc([[1, title, page] for title, page in doc.heading_pages])
    finalized = OUTPUT.with_name(OUTPUT.stem + ".finalized.pdf")
    navigation.save(finalized, garbage=4, deflate=True)
finalized.replace(OUTPUT)

with pymupdf.open(OUTPUT) as pdf:
    for number, page in enumerate(pdf, 1):
        page.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7), alpha=False).save(QA / f"page-{number:02d}.png")
    print("PDF pages:", len(pdf))
    print("Section starts:")
    for title, page in doc.heading_pages: print(page, title)
    text = "\n".join(page.get_text() for page in pdf)
    (QA / "extracted-text.txt").write_text(text, encoding="utf-8")
    assert all(term in text for term in ["Batch uploads and analysis", "Document chat and local retrieval", "Evidence highlighting and human review", "111 tests", "2030-01-12"])
    assert len(pdf) >= 14
    for first in range(1, len(pdf) + 1, 7):
        sheet = Image.new("RGB", (2 * 430, 4 * 625), "#d6d8d0")
        draw = ImageDraw.Draw(sheet)
        for k, page_number in enumerate(range(first, min(first + 7, len(pdf) + 1))):
            with Image.open(QA / f"page-{page_number:02d}.png") as page_image:
                page_image.thumbnail((410, 583))
                x, y = (k % 2) * 430 + 10, (k // 2) * 625 + 28
                sheet.paste(page_image, (x, y)); draw.text((x, y - 19), f"PAGE {page_number}", fill="black")
        sheet.save(QA / f"contact-{first:02d}.png")
    print("Output:", OUTPUT)
    print("QA:", QA)
