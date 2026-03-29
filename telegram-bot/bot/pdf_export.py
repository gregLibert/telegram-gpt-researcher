"""Render Markdown as a formatted PDF (HTML intermediate) for Telegram delivery."""

from __future__ import annotations

from io import BytesIO
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import markdown
from fpdf import FPDF
from fpdf.fonts import FontFace, TextStyle
from fpdf.html import DEFAULT_TAG_STYLES

# Typical paths when DejaVu is installed (e.g. Debian/Ubuntu Docker images).
_DEBIAN_DEJAVU = Path("/usr/share/fonts/truetype/dejavu")


def _resolve_dejavu_regular_path() -> Path | None:
    """Locate ``DejaVuSans.ttf`` from common Linux paths or optional fpdf package data."""
    candidate = _DEBIAN_DEJAVU / "DejaVuSans.ttf"
    if candidate.is_file():
        return candidate
    try:
        ref = files("fpdf").joinpath("font", "DejaVuSans.ttf")
        with as_file(ref) as extracted:
            p = Path(extracted)
            if p.is_file():
                return p
    except (FileNotFoundError, ModuleNotFoundError, OSError, ValueError):
        pass
    return None


def _register_dejavu_family(pdf: FPDF) -> bool:
    """
    Register DejaVu Sans (plus common styles) if TTF files are available on disk.

    The PyPI ``fpdf2`` wheel does not ship font binaries; Linux images often provide
    ``fonts-dejavu-core``. When registration fails, callers should fall back to core fonts.
    """
    regular = _resolve_dejavu_regular_path()
    if regular is None:
        return False
    font_dir = regular.parent
    bold = font_dir / "DejaVuSans-Bold.ttf"
    italic = font_dir / "DejaVuSans-Oblique.ttf"
    bold_italic = font_dir / "DejaVuSans-BoldOblique.ttf"
    try:
        pdf.add_font("dejavu", "", str(regular))
        if bold.is_file():
            pdf.add_font("dejavu", "B", str(bold))
        if italic.is_file():
            pdf.add_font("dejavu", "I", str(italic))
        if bold_italic.is_file():
            pdf.add_font("dejavu", "BI", str(bold_italic))
        pdf.set_font("dejavu", size=11)
        return True
    except OSError:
        return False


def _unicode_html_tag_styles() -> dict[str, Any]:
    """Clone fpdf2 default HTML styles but force the registered ``dejavu`` family."""
    styles: dict[str, Any] = {}
    for tag, style in DEFAULT_TAG_STYLES.items():
        if isinstance(style, TextStyle):
            styles[tag] = style.replace(font_family="dejavu")
        elif isinstance(style, FontFace):
            if tag == "code":
                styles[tag] = style
            else:
                styles[tag] = style.replace(family="dejavu")
        else:
            styles[tag] = style
    return styles


def _markdown_to_html_fragment(markdown_text: str) -> str:
    """Turn Markdown into an HTML fragment suitable for :meth:`FPDF.write_html`."""
    body = markdown_text if markdown_text.strip() else "(rapport vide)"
    return markdown.markdown(
        body,
        extensions=["extra", "nl2br", "sane_lists"],
    )


def _coerce_html_to_latin1(html: str) -> str:
    """Force HTML text to something core PDF fonts can encode (lossy fallback)."""
    return html.encode("latin-1", errors="replace").decode("latin-1")


def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    """
    Build a PDF from Markdown via HTML, preserving common structure (headings, emphasis, links).

    Uses the ``markdown`` package and fpdf2's ``write_html``. When DejaVu TTF files are
    available, Unicode and styled headings work; otherwise content is coerced for core fonts.
    """
    html = _markdown_to_html_fragment(markdown_text)

    pdf = FPDF()
    pdf.set_compression(False)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    tag_styles: dict[str, Any] | None = None
    if _register_dejavu_family(pdf):
        tag_styles = _unicode_html_tag_styles()
    else:
        html = _coerce_html_to_latin1(html)

    pdf.write_html(html, tag_styles=tag_styles)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


markdown_to_basic_pdf_bytes = markdown_to_pdf_bytes
