"""Safe basename fragments for downloadable artifacts."""

from __future__ import annotations

import re


def sanitize_download_basename(value: str, *, max_len: int = 48) -> str:
    """
    Produce a filesystem-friendly basename fragment (no path separators).

    Non-word characters (except whitespace and hyphen) are removed; whitespace
    collapses to underscores. Falls back to ``research`` if nothing remains.
    """
    s = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip()
    s = re.sub(r"\s+", "_", s)
    return (s or "research")[:max_len]
