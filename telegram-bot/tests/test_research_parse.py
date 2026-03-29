"""Table-driven tests for /research argv parsing (match/case options)."""

from __future__ import annotations

import pytest

from bot.research_parse import ParsedResearchCommand, parse_research_command


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], None),
        ([""], None),
        (["   "], None),
        (
            ["What", "is", "Docker?"],
            ParsedResearchCommand(query="What is Docker?", report_type="research_report"),
        ),
        (
            ["--deep", "topic"],
            ParsedResearchCommand(query="topic", report_type="deep"),
        ),
        (
            ["-d", "topic"],
            ParsedResearchCommand(query="topic", report_type="deep"),
        ),
        (
            ["--detailed", "x"],
            ParsedResearchCommand(query="x", report_type="detailed_report"),
        ),
        (
            ["--outline", "x", "y"],
            ParsedResearchCommand(query="x y", report_type="outline_report"),
        ),
        (
            ["--resource", "links"],
            ParsedResearchCommand(query="links", report_type="resource_report"),
        ),
        (
            ["--deep", "--outline", "q"],
            ParsedResearchCommand(query="q", report_type="outline_report"),
        ),
        (
            ["deep", "learning"],
            ParsedResearchCommand(query="deep learning", report_type="research_report"),
        ),
    ],
)
def test_parse_research_command(
    argv: list[str],
    expected: ParsedResearchCommand | None,
) -> None:
    assert parse_research_command(argv) == expected
