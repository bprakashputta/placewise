"""Turn a resume file into clean text, without any AI.

- Detects the real type from the file's bytes (not its extension).
- PDF: separates HIDDEN text (white or tiny glyphs, a common prompt-injection trick) from visible
  text; reads two-column layouts column by column instead of interleaving lines; flags scans
  (no text layer) as needing OCR.
- DOCX: paragraphs and table cells (two-column Word resumes are usually tables).
- Corrupt or unreadable files come back as status='unusable' with a reason, never an exception.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field


@dataclass
class Parsed:
    status: str                      # ok | unusable
    file_type: str                   # pdf | docx | txt | unknown
    text: str = ""                   # visible text only
    hidden_text: str = ""            # text a human can't see (PDF)
    reason: str | None = None        # why unusable
    pages: int = 0
    columns_detected: bool = False
    issues: list[str] = field(default_factory=list)


def sniff(data: bytes) -> str:
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:2] == b"PK":
        return "docx"
    try:
        data[:4000].decode("utf-8")
        return "txt"
    except UnicodeDecodeError:
        return "unknown"


def _is_hidden(ch: dict) -> bool:
    """White (or near-white) fill, or a glyph too small to read."""
    if ch.get("size", 10) < 3:
        return True
    color = ch.get("non_stroking_color")
    if color is None:
        return False
    vals = color if isinstance(color, (list, tuple)) else (color,)
    try:
        vals = [float(v) for v in vals]
    except (TypeError, ValueError):
        return False
    if len(vals) == 1:
        return vals[0] >= 0.97                      # gray scale: 1 = white
    if len(vals) == 3:
        return min(vals) >= 0.97                    # RGB white
    if len(vals) == 4:
        return max(vals) <= 0.03                    # CMYK with no ink = white
    return False


def _column_split(words: list[dict], width: float) -> float | None:
    """Find a vertical gutter between 20% and 55% of the page that no word crosses."""
    if len(words) < 40:
        return None
    for x in range(int(width * 0.20), int(width * 0.55), 3):
        if any(w["x0"] < x < w["x1"] for w in words):
            continue
        left = sum(1 for w in words if w["x1"] <= x)
        right = sum(1 for w in words if w["x0"] >= x)
        if left >= 15 and right >= 15:
            return float(x)
    return None


def parse_pdf(data: bytes) -> Parsed:
    import pdfplumber

    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as e:
        return Parsed("unusable", "pdf", reason=f"corrupt PDF ({type(e).__name__})")
    visible_parts, hidden_parts, columns, has_images = [], [], False, False
    with pdf:
        for page in pdf.pages:
            has_images = has_images or bool(page.images)
            hidden = "".join(c["text"] for c in page.chars if _is_hidden(c)).strip()
            if hidden:
                hidden_parts.append(hidden)
            vis = page.filter(lambda o: o.get("object_type") != "char" or not _is_hidden(o))
            words = vis.extract_words()
            split = _column_split(words, page.width)
            if split:
                columns = True
                left = vis.crop((0, 0, split, page.height)).extract_text() or ""
                right = vis.crop((split, 0, page.width, page.height)).extract_text() or ""
                visible_parts.append(left + "\n\n" + right)
            else:
                visible_parts.append(vis.extract_text() or "")
        pages = len(pdf.pages)
    text = "\n\n".join(p for p in visible_parts if p).strip()
    hidden_text = " ".join(hidden_parts)
    if len(text) < 40:
        reason = "no text layer: looks like a scanned image (needs OCR)" if has_images else "PDF has no readable text"
        return Parsed("unusable", "pdf", text=text, hidden_text=hidden_text, reason=reason, pages=pages)
    return Parsed("ok", "pdf", text=text, hidden_text=hidden_text, pages=pages, columns_detected=columns)


def parse_docx(data: bytes) -> Parsed:
    from docx import Document

    if not zipfile.is_zipfile(io.BytesIO(data)):
        return Parsed("unusable", "docx", reason="corrupt DOCX (not a valid archive)")
    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:
        return Parsed("unusable", "docx", reason=f"corrupt DOCX ({type(e).__name__})")
    visible, hidden = [], []

    def run_hidden(run) -> bool:
        f = run.font
        if f.hidden:
            return True
        if f.size is not None and f.size.pt < 3:
            return True
        rgb = f.color.rgb if f.color is not None and f.color.type is not None else None
        return rgb is not None and str(rgb).upper() in ("FFFFFF", "FEFEFE", "FDFDFD")

    def add(paragraph) -> None:
        vis = "".join(r.text for r in paragraph.runs if not run_hidden(r))
        hid = "".join(r.text for r in paragraph.runs if run_hidden(r))
        visible.append(vis if paragraph.runs else paragraph.text)
        if hid.strip():
            hidden.append(hid.strip())

    for p in doc.paragraphs:
        add(p)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    add(p)
    text = "\n".join(visible).strip()
    if len(text) < 40:
        return Parsed("unusable", "docx", text=text, hidden_text=" ".join(hidden), reason="DOCX has almost no text")
    return Parsed("ok", "docx", text=text, hidden_text=" ".join(hidden))


def parse_txt(data: bytes) -> Parsed:
    text = data.decode("utf-8", errors="replace").strip()
    if len(text) < 40:
        return Parsed("unusable", "txt", text=text, reason="text file is almost empty")
    return Parsed("ok", "txt", text=text)


def parse(data: bytes) -> Parsed:
    kind = sniff(data)
    if kind == "pdf":
        result = parse_pdf(data)
    elif kind == "docx":
        result = parse_docx(data)
    elif kind == "txt":
        result = parse_txt(data)
    else:
        return Parsed("unusable", "unknown", reason="unsupported or binary file type")
    result.text = re.sub(r"[ \t]+\n", "\n", result.text)
    result.text = re.sub(r"\n{3,}", "\n\n", result.text)
    return result
