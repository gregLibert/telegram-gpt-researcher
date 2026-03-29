"""Table-driven tests for Markdown-to-PDF generation (WeasyPrint)."""

from __future__ import annotations

import pytest

try:
    from bot.pdf_export import markdown_to_basic_pdf_bytes, markdown_to_pdf_bytes
except OSError:
    pytest.skip("WeasyPrint system libraries unavailable", allow_module_level=True)


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
    ("markdown", "min_size"),
    [
        ("(rapport vide)", 500),
        ("UniqueLine", 500),
    ],
)
def test_markdown_to_basic_pdf_bytes_non_trivial_size(
    markdown: str,
    min_size: int,
) -> None:
    pdf_bytes = markdown_to_basic_pdf_bytes(markdown)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) >= min_size


@pytest.mark.parametrize(
    "markdown",
    [
        "# Heading\n\nParagraph with **bold** and *italic*.\n",
        "| a | b |\n|---|---|\n| 1 | 2 |\n",
        "[Example](https://example.com/long/path/" + "x" * 80 + ")\n",
    ],
)
def test_markdown_to_pdf_bytes_tables_and_links(markdown: str) -> None:
    data = markdown_to_pdf_bytes(markdown)
    assert data.startswith(b"%PDF")
    assert len(data) > 200


def test_markdown_to_pdf_bytes_alias_matches_public_api() -> None:
    assert markdown_to_basic_pdf_bytes is markdown_to_pdf_bytes
