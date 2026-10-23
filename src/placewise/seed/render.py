"""Render structured resumes into professional PDF / DOCX / TXT files.

Five templates (classic, modern, two_column, compact, ats_plain). Because the writer returns
structured fields, the layout never has to guess what is a title, a company or a date.

Deliberate hard cases for the ingest pipeline:
- two-column PDFs (text extraction may interleave the columns),
- hidden prompt-injection text (white, 1pt) in some PDFs,
- image-only PDFs (no text layer) and truncated, corrupt DOCX files.
DOCX/TXT files also get a PDF preview copy so the Seed page can show every resume in-browser.
Every file's metadata marks it as synthetic test data.
"""
from __future__ import annotations

import hashlib
import io
import textwrap
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, HRFlowable, KeepTogether,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

from .facts import CandidateFacts
from .noise import INJECTION_TEXT, rng_for

SYNTHETIC_NOTE = "SYNTHETIC test resume generated for Placewise. Not a real person."
PREVIEW_NAME = "_preview.pdf"
W, H = LETTER
MARGIN = 0.65 * inch

THEMES = {
    "classic": dict(font="Times-Roman", bold="Times-Bold", italic="Times-Italic", size=10.5, accent="#111827",
                    muted="#374151", name_size=21, center=True, rule=0.6),
    "modern": dict(font="Helvetica", bold="Helvetica-Bold", italic="Helvetica-Oblique", size=9.8, accent="#3730a3",
                   muted="#4b5563", name_size=23, center=False, rule=1.0),
    "two_column": dict(font="Helvetica", bold="Helvetica-Bold", italic="Helvetica-Oblique", size=9.5,
                       accent="#0f766e", muted="#475569", name_size=22, center=False, rule=0.8),
    "compact": dict(font="Helvetica", bold="Helvetica-Bold", italic="Helvetica-Oblique", size=8.8, accent="#1f2937",
                    muted="#4b5563", name_size=16, center=False, rule=0.5),
    "ats_plain": dict(font="Helvetica", bold="Helvetica-Bold", italic="Helvetica", size=10, accent="#000000",
                      muted="#000000", name_size=14, center=False, rule=0),
}


@dataclass
class Rendered:
    candidate_id: str
    path: str
    file_format: str
    template: str
    bytes: int
    sha256: str
    note: str = ""
    preview: str | None = None


# ----------------------------------------------------------------------------- PDF

def _st(t: dict) -> dict[str, ParagraphStyle]:
    s, acc, mut = t["size"], colors.HexColor(t["accent"]), colors.HexColor(t["muted"])
    align = TA_CENTER if t["center"] else 0
    return {
        "name": ParagraphStyle("name", fontName=t["bold"], fontSize=t["name_size"], leading=t["name_size"] + 3,
                               textColor=acc, alignment=align),
        "headline": ParagraphStyle("hl", fontName=t["italic"], fontSize=s + 1, leading=s + 4, textColor=mut,
                                   alignment=align, spaceBefore=2),
        "contact": ParagraphStyle("ct", fontName=t["font"], fontSize=s - 0.8, leading=s + 2, textColor=mut,
                                  alignment=align, spaceBefore=2),
        "h": ParagraphStyle("h", fontName=t["bold"], fontSize=s + 1, leading=s + 4, textColor=acc,
                            spaceBefore=s * 0.9, spaceAfter=1),
        "body": ParagraphStyle("b", fontName=t["font"], fontSize=s, leading=s * 1.35),
        "title": ParagraphStyle("t", fontName=t["bold"], fontSize=s + 0.4, leading=s * 1.35),
        "org": ParagraphStyle("o", fontName=t["italic"], fontSize=s, leading=s * 1.3, textColor=mut),
        "date": ParagraphStyle("d", fontName=t["font"], fontSize=s - 0.4, leading=s * 1.35, textColor=mut,
                               alignment=TA_RIGHT),
        "bullet": ParagraphStyle("bl", fontName=t["font"], fontSize=s, leading=s * 1.32, leftIndent=11,
                                 bulletIndent=1, spaceBefore=1),
        "side_h": ParagraphStyle("sh", fontName=t["bold"], fontSize=s, leading=s + 3, textColor=acc,
                                 spaceBefore=s, spaceAfter=2),
        "side": ParagraphStyle("sb", fontName=t["font"], fontSize=s - 0.6, leading=s * 1.3),
    }


def _p(text: str, style) -> Paragraph:
    return Paragraph(escape(text), style)


def _heading(text: str, st, t, template) -> list:
    out = [_p(text.upper() if template in ("classic", "ats_plain", "compact") else text, st["h"])]
    if t["rule"]:
        out.append(HRFlowable(width="100%", thickness=t["rule"], color=colors.HexColor(t["accent"]),
                              spaceBefore=1, spaceAfter=3))
    return out


def _table(rows, width: float) -> Table:
    tbl = Table(rows, colWidths=[width - 1.55 * inch, 1.55 * inch])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5)]))
    return tbl


def _job(job: dict, st, width: float, bullet: str, template: str) -> list:
    dates = f"{job['start']} – {job['end']}"
    if template == "ats_plain":
        head = [_p(f"{job['title']} | {job['employer']} | {job['location']} | {dates}", st["title"])]
    elif template == "compact":
        head = [_table([[Paragraph(f"<b>{escape(job['title'])}</b>, {escape(job['employer'])} · "
                                   f"{escape(job['location'])}", st["body"]), _p(dates, st["date"])]], width)]
    else:
        head = [_table([[_p(job["title"], st["title"]), _p(dates, st["date"])],
                        [_p(f"{job['employer']} · {job['location']}", st["org"]), ""]], width)]
    bullets = [Paragraph(escape(b), st["bullet"], bulletText=bullet) for b in job["bullets"]]
    # Keep the job header with its first bullet so headers never strand at a page bottom
    return [KeepTogether(head + bullets[:1]), *bullets[1:], Spacer(1, st["body"].fontSize * 0.5)]


def _header(r: dict, st) -> list:
    return [_p(r["name"], st["name"]), _p(r["headline"], st["headline"]),
            _p("  ·  ".join(r["contact"]), st["contact"]), Spacer(1, 4)]


def _section(heading: list, content: list) -> list:
    """Keep a heading on the same page as its first piece of content (no stranded headings).
    Nested KeepTogether blocks make ReportLab push whole sections to the next page, so the
    first item's contents are spliced in rather than nested."""
    if not content:
        return []
    first = content[0]
    inner = list(first._content) if isinstance(first, KeepTogether) else [first]
    return [KeepTogether(heading + inner), *content[1:]]


def _main_sections(r: dict, st, t, template, width, bullet, include_side: bool) -> list:
    out = _section(_heading(r["summary_heading"], st, t, template), [_p(r["summary"], st["body"])])
    jobs = [f for job in r["jobs"] for f in _job(job, st, width, bullet, template)]
    out += _section(_heading(r["experience_heading"], st, t, template), jobs)
    if include_side:
        if r["skills"]:
            out += _section(_heading(r["skills_heading"], st, t, template), [_p(" · ".join(r["skills"]), st["body"])])
        if r["credentials"]:
            out += _section(_heading(r["credentials_heading"], st, t, template),
                            [Paragraph(escape(c), st["bullet"], bulletText=bullet) for c in r["credentials"]])
        out += _section(_heading(r["education_heading"], st, t, template),
                        [Paragraph(f"<b>{escape(e['degree'])}</b>, {escape(e['school'])}, {escape(e['year'])}",
                                   st["body"]) for e in r["education"]])
    for sec in r.get("extra_sections", []):
        out += _section(_heading(sec["heading"], st, t, template),
                        [Paragraph(escape(i), st["bullet"], bulletText=bullet) for i in sec["items"]])
    return out


def render_pdf(r: dict, c: CandidateFacts, template: str, bullet: str = "•") -> bytes:
    t = THEMES[template]
    st = _st(t)
    buf = io.BytesIO()
    meta = dict(title=f"Resume - {c.full_name}", author=c.full_name, subject=SYNTHETIC_NOTE,
                creator="Placewise synthetic data generator")

    def decorate(canv, _doc):
        if template == "two_column":
            canv.saveState()
            canv.setFillColor(colors.HexColor("#f1f5f9"))
            canv.rect(0, 0, MARGIN + 2.25 * inch, H, stroke=0, fill=1)
            canv.restoreState()
        if c.injection:
            canv.saveState()
            canv.setFillColor(colors.white)
            canv.setFont("Helvetica", 1)
            canv.drawString(MARGIN, 0.3 * inch, INJECTION_TEXT)
            canv.restoreState()

    # invariant=1: no timestamp/random document ID, so the same resume always renders to the same
    # bytes (hash-based idempotency in ingest depends on this)
    doc = BaseDocTemplate(buf, pagesize=LETTER, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=0.6 * inch,
                          bottomMargin=0.6 * inch, invariant=1, **meta)
    full_w = W - 2 * MARGIN
    fh = H - doc.topMargin - doc.bottomMargin
    if template == "two_column":
        side_w, gap = 2.0 * inch, 0.45 * inch
        main_w = full_w - side_w - gap
        side = Frame(MARGIN, doc.bottomMargin, side_w, fh, id="side", leftPadding=0, rightPadding=0)
        main = Frame(MARGIN + side_w + gap, doc.bottomMargin, main_w, fh, id="main", leftPadding=0, rightPadding=0)
        later = Frame(MARGIN + side_w + gap, doc.bottomMargin, main_w, fh, id="later", leftPadding=0,
                      rightPadding=0)
        doc.addPageTemplates([PageTemplate(id="first", frames=[side, main], onPage=decorate,
                                           autoNextPageTemplate="later"),
                              PageTemplate(id="later", frames=[later], onPage=decorate)])
        sidebar = [_p("Contact", st["side_h"]), *[_p(x, st["side"]) for x in r["contact"]]]
        if r["skills"]:
            sidebar += [_p(r["skills_heading"], st["side_h"]), *[_p(x, st["side"]) for x in r["skills"]]]
        if r["credentials"]:
            sidebar += [_p(r["credentials_heading"], st["side_h"]), *[_p(x, st["side"]) for x in r["credentials"]]]
        sidebar += [_p(r["education_heading"], st["side_h"])]
        for e in r["education"]:
            sidebar += [Paragraph(f"<b>{escape(e['degree'])}</b>", st["side"]),
                        _p(f"{e['school']}, {e['year']}", st["side"]), Spacer(1, 3)]
        story = sidebar + [FrameBreak(), _p(r["name"], st["name"]), _p(r["headline"], st["headline"]),
                           Spacer(1, 6), *_main_sections(r, st, t, template, main_w, bullet, include_side=False)]
    else:
        doc.addPageTemplates([PageTemplate(id="one", frames=[Frame(MARGIN, doc.bottomMargin, full_w, fh,
                                                                   leftPadding=0, rightPadding=0)],
                                           onPage=decorate)])
        story = _header(r, st) + _main_sections(r, st, t, template, full_w, bullet, include_side=True)
    doc.build(story)
    return buf.getvalue()


def render_image_pdf(text: str, c: CandidateFacts) -> bytes:
    """A 'scanned' resume: the page is a picture of text, with no selectable text layer."""
    for a, b in {"–": "-", "—": "-", "•": "*", "◦": "o", "’": "'", "“": '"',
                 "”": '"', "·": "|"}.items():
        text = text.replace(a, b)
    lines = [w for ln in text.splitlines() for w in (textwrap.wrap(ln, 92) or [""])][:68]
    font = ImageFont.load_default(size=22)
    img = Image.new("L", (1700, 2200), 250)
    draw = ImageDraw.Draw(img)
    y = 90
    for ln in lines:
        draw.text((110, y), ln, fill=20, font=font)
        y += 30
    img = img.rotate(0.4, fillcolor=250)  # a scan is never perfectly straight
    png = io.BytesIO()
    img.save(png, format="PNG")
    png.seek(0)
    buf = io.BytesIO()
    cv = rl_canvas.Canvas(buf, pagesize=LETTER, invariant=1)
    cv.setTitle(f"Scan - {c.full_name}")
    cv.setSubject(SYNTHETIC_NOTE)
    cv.drawImage(ImageReader(png), 0, 0, width=W, height=H)
    cv.showPage()
    cv.save()
    return buf.getvalue()


# ----------------------------------------------------------------------------- DOCX

def _border_bottom(paragraph, color="3730A3", size=6):
    p_pr = paragraph._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", str(size)), ("w:space", "1"), ("w:color", color)):
        bottom.set(qn(k), v)
    bdr.append(bottom)
    p_pr.append(bdr)


def _shade(cell, fill="F1F5F9"):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def render_docx(r: dict, c: CandidateFacts, template: str, bullet: str = "•") -> bytes:
    t = THEMES[template]
    accent = RGBColor.from_string(t["accent"].lstrip("#").upper())
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(0.7)
        s.top_margin = s.bottom_margin = Inches(0.6)
    doc.core_properties.title = f"Resume - {c.full_name}"
    doc.core_properties.author = c.full_name
    doc.core_properties.comments = SYNTHETIC_NOTE
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman" if template == "classic" else "Calibri"
    normal.font.size = Pt(t["size"] + 0.5)
    normal.paragraph_format.space_after = Pt(2)
    text_width = Inches(8.5 - 1.4)

    def para(container, text="", bold=False, italic=False, size=None, color=None, after=2):
        p = container.add_paragraph()
        p.paragraph_format.space_after = Pt(after)
        if text:
            run = p.add_run(text)
            run.bold, run.italic = bold, italic
            if size:
                run.font.size = Pt(size)
            if color is not None:
                run.font.color.rgb = color
        return p

    def heading(container, text):
        p = para(container, text if template == "modern" else text.upper(), bold=True, size=t["size"] + 2,
                 color=accent if template != "ats_plain" else None, after=3)
        p.paragraph_format.space_before = Pt(8)
        if template != "ats_plain":
            _border_bottom(p, t["accent"].lstrip("#").upper())

    def job(container, j, width):
        p = para(container, after=0)
        p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        p.add_run(j["title"]).bold = True
        p.add_run(f"\t{j['start']} – {j['end']}")
        para(container, f"{j['employer']} · {j['location']}", italic=True, after=1)
        for b in j["bullets"]:
            bp = container.add_paragraph(style="List Bullet")
            bp.paragraph_format.space_after = Pt(1)
            bp.add_run(b)

    header = [para(doc, r["name"], bold=True, size=t["name_size"] - 1,
                   color=accent if template in ("modern", "two_column") else None, after=0),
              para(doc, r["headline"], italic=True, size=t["size"] + 1, after=0),
              para(doc, "  ·  ".join(r["contact"]), size=t["size"] - 0.5, after=4)]
    if t["center"]:
        for p in header:
            p.alignment = 1

    def side_content(container):
        if r["skills"]:
            heading(container, r["skills_heading"])
            para(container, " · ".join(r["skills"]))
        if r["credentials"]:
            heading(container, r["credentials_heading"])
            for x in r["credentials"]:
                para(container, x, after=1)
        heading(container, r["education_heading"])
        for e in r["education"]:
            para(container, f"{e['degree']}, {e['school']}, {e['year']}", after=1)

    def main_content(container, width):
        heading(container, r["summary_heading"])
        para(container, r["summary"])
        heading(container, r["experience_heading"])
        for j in r["jobs"]:
            job(container, j, width)
        for sec in r.get("extra_sections", []):
            heading(container, sec["heading"])
            for i in sec["items"]:
                container.add_paragraph(i, style="List Bullet")

    if template == "two_column":
        table = doc.add_table(rows=1, cols=2)
        table.autofit = False
        left, right = table.cell(0, 0), table.cell(0, 1)
        left.width, right.width = Inches(2.2), Inches(4.9)
        _shade(left)
        side_content(left)
        main_content(right, Inches(4.7))
    else:
        main_content(doc, text_width)
        side_content(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ----------------------------------------------------------------------------- files

def filename_for(c: CandidateFacts, ext: str) -> str:
    rng = rng_for(c.candidate_id, "filename")
    f, last = c.first_name, c.last_name
    return rng.choice([f"{f}_{last}_Resume.{ext}", f"{last}{f}-resume-2026.{ext}", f"Resume - {f} {last}.{ext}",
                       f"CV_{f.upper()}_{last.upper()}.{ext}", f"{f.lower()}.{last.lower()}.resume.{ext}",
                       f"{f} {last} Resume (updated).{ext}"])


def render_file(resume: dict, text: str, c: CandidateFacts, out_root: Path, bullet: str = "•") -> Rendered:
    template, file_format = c.style.template, c.style.file_format
    note, preview = "", None
    folder = out_root / c.candidate_id
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.iterdir():
        old.unlink()
    if c.unreadable == "image_pdf":
        data, file_format, note = render_image_pdf(text, c), "pdf", "image-only PDF (no text layer)"
    elif file_format == "pdf":
        data = render_pdf(resume, c, template, bullet)
        note = "hidden injection text" if c.injection else ""
    elif file_format == "docx":
        data = render_docx(resume, c, template, bullet)
        if c.unreadable == "corrupt_docx":
            data, note = data[: int(len(data) * 0.6)], "truncated DOCX (corrupt)"
    else:
        data = (text + "\n").encode("utf-8")
    path = folder / filename_for(c, file_format)
    path.write_bytes(data)
    # In-browser preview for DOCX/TXT (not for the corrupt file: it can't be opened, by design)
    if file_format in ("docx", "txt") and c.unreadable != "corrupt_docx":
        (folder / PREVIEW_NAME).write_bytes(render_pdf(resume, c, template, bullet))
        preview = f"{c.candidate_id}/{PREVIEW_NAME}"
    return Rendered(candidate_id=c.candidate_id, path=str(path.relative_to(out_root)), file_format=file_format,
                    template=template, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), note=note,
                    preview=preview)
