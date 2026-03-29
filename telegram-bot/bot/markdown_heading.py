"""Extract human-readable titles from Markdown source text."""

from __future__ import annotations

import re

_ATX_HEADING = re.compile(r"^(?P<hashes>#{1,2})\s+(?P<title>.+?)\s*$")


def extract_first_markdown_heading_title(markdown_text: str) -> str | None:
    """
    Return the text of the first ATX heading of level 1 or 2 (``#`` / ``##``).

    Lines are scanned in order; leading/trailing blank lines are ignored per line.
    Returns ``None`` if no such heading exists.
    """
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _ATX_HEADING.match(line)
        if match:
            return match.group("title").strip()
    return None
