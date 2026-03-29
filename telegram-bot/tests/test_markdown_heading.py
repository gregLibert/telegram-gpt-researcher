"""Table-driven tests for Markdown heading extraction."""

from __future__ import annotations

import pytest

from bot.markdown_heading import extract_first_markdown_heading_title


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("", None),
        ("No heading here", None),
        ("### Too deep\n", None),
        ("# Hello World\n", "Hello World"),
        ("## Section A\n", "Section A"),
        ("\n\n# First\n\n## Second\n", "First"),
        ("Intro line\n## Subtitle\n", "Subtitle"),
        ("#  Trimmed  \n", "Trimmed"),
    ],
)
def test_extract_first_markdown_heading_title(markdown: str, expected: str | None) -> None:
    assert extract_first_markdown_heading_title(markdown) == expected
