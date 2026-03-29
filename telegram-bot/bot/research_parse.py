"""Parse /research command arguments (optional flags + free-text query)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedResearchCommand:
    """Normalized research request derived from Telegram command argv."""

    query: str
    report_type: str


def parse_research_command(argv: list[str]) -> ParsedResearchCommand | None:
    """
    Parse ``context.args`` for /research.

    Leading option tokens (``--deep``, ``-d``, etc.) select ``report_type`` for the
    GPT Researcher API. The remainder is joined into the task string. Only
    long-form flags are accepted as bare words (except ``-d``) so phrases like
    ``deep learning`` are not mistaken for the deep-research mode.
    """
    if not argv:
        return None

    rest = list(argv)
    report_type = "research_report"

    while rest:
        token = rest[0]
        match token:
            case "--deep" | "-d":
                report_type = "deep"
                rest = rest[1:]
            case "--detailed":
                report_type = "detailed_report"
                rest = rest[1:]
            case "--outline":
                report_type = "outline_report"
                rest = rest[1:]
            case "--resource":
                report_type = "resource_report"
                rest = rest[1:]
            case _:
                break

    query = " ".join(rest).strip()
    if not query:
        return None

    return ParsedResearchCommand(query=query, report_type=report_type)
