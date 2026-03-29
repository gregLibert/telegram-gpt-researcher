"""Table-driven tests for minimal PDF generation."""

from __future__ import annotations

import pytest

from bot.pdf_export import markdown_to_basic_pdf_bytes


@pytest.mark.parametrize(
    "markdown",
    [
        "Hello\n\nWorld",
        "# Title\n\nParagraph **bold**.",
        "",
        "   \n\t  ",
        "Résumé : été à Zürich — €100.",
    ],
)
def test_markdown_to_basic_pdf_bytes_starts_with_pdf_signature(markdown: str) -> None:
    pdf_bytes = markdown_to_basic_pdf_bytes(markdown)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 200


@pytest.mark.parametrize(
    ("markdown", "needle"),
    [
        ("(rapport vide)", b"rapport"),  # placeholder path still yields PDF structure
        ("UniqueLine", b"UniqueLine"),
    ],
)
def test_markdown_to_basic_pdf_bytes_embeds_text_content(
    markdown: str,
    needle: bytes,
) -> None:
    pdf_bytes = markdown_to_basic_pdf_bytes(markdown)
    assert needle in pdf_bytes
