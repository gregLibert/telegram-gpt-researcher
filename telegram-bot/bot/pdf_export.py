"""Render Markdown as a minimal UTF-8 text PDF for Telegram delivery."""

from __future__ import annotations

from io import BytesIO
from importlib.resources import as_file, files

from fpdf import FPDF


def _with_dejavu_font(pdf: FPDF) -> bool:
    """Register DejaVu Sans when the bundled font is available."""
    try:
        ref = files("fpdf").joinpath("font", "DejaVuSans.ttf")
        with as_file(ref) as font_path:
            pdf.add_font("DejaVu", "", str(font_path))
        pdf.set_font("DejaVu", size=11)
        return True
    except (FileNotFoundError, ModuleNotFoundError, OSError, ValueError):
        return False


def markdown_to_basic_pdf_bytes(markdown: str) -> bytes:
    """
    Build a simple PDF from Markdown (plain-text layout, not rich formatting).

    Empty or whitespace-only input is rendered as a placeholder line.
    """
    text = markdown if markdown.strip() else "(rapport vide)"

    pdf = FPDF()
    pdf.set_compression(False)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    has_unicode_font = _with_dejavu_font(pdf)
    if not has_unicode_font:
        pdf.set_font("Helvetica", size=11)

    usable_width = pdf.epw
    line_height = 6
    for line in text.splitlines():
        safe = (
            line
            if has_unicode_font
            else line.encode("latin-1", errors="replace").decode("latin-1")
        )
        pdf.multi_cell(usable_width, line_height, safe or " ")

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
