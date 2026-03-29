"""Parse Telegram user allowlists from environment-style strings."""

from __future__ import annotations


def parse_allowed_user_ids(raw: str) -> set[int]:
    """
    Parse a comma- or semicolon-separated list of integer Telegram user IDs.

    Empty segments are ignored. Whitespace around entries is stripped.
    """
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        out.add(int(part))
    return out
