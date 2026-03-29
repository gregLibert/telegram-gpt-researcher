"""Table-driven tests for GPT Researcher delivery metadata parsing."""

from __future__ import annotations

import pytest

from bot.gptr_client import ResearchDeliveryMeta, format_delivery_summary, parse_research_delivery_meta


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"research_information": None},
    ],
)
def test_parse_research_delivery_meta_empty(payload: dict) -> None:
    result = parse_research_delivery_meta(payload)
    assert result == ResearchDeliveryMeta(
        estimated_total_usd=None,
        source_urls=(),
        visited_urls=(),
        step_costs=(),
    )


def test_parse_research_delivery_meta_full_research_information() -> None:
    payload = {
        "research_information": {
            "research_costs": 0.0123,
            "source_urls": ["https://a.example", "https://b.example"],
            "visited_urls": ["https://x.example"],
        }
    }
    result = parse_research_delivery_meta(payload)
    assert result.estimated_total_usd == pytest.approx(0.0123)
    assert result.source_urls == ("https://a.example", "https://b.example")
    assert result.visited_urls == ("https://x.example",)
    assert result.step_costs == ()


def test_parse_research_delivery_meta_dict_costs_sums_steps() -> None:
    payload = {
        "research_information": {
            "research_costs": {"embed": 0.01, "chat": 0.02},
        }
    }
    result = parse_research_delivery_meta(payload)
    assert result.estimated_total_usd == pytest.approx(0.03)
    assert set(result.step_costs) == {("embed", 0.01), ("chat", 0.02)}


def test_parse_research_delivery_meta_metadata_fallback() -> None:
    payload = {"metadata": {"total_cost": 1.5}}
    result = parse_research_delivery_meta(payload)
    assert result.estimated_total_usd == pytest.approx(1.5)


@pytest.mark.parametrize(
    ("meta", "must_contain"),
    [
        (
            ResearchDeliveryMeta(
                estimated_total_usd=0.02,
                source_urls=("https://a",),
                visited_urls=("u1", "u2", "u3"),
                step_costs=(),
            ),
            ["Estimated Cost: $0.0200", "Sources: 1", "Visited URLs: 3"],
        ),
        (
            ResearchDeliveryMeta(
                estimated_total_usd=None,
                source_urls=(),
                visited_urls=(),
                step_costs=(),
            ),
            [],
        ),
    ],
)
def test_format_delivery_summary(meta: ResearchDeliveryMeta, must_contain: list[str]) -> None:
    text = format_delivery_summary(meta)
    for part in must_contain:
        assert part in text
    if not must_contain:
        assert text == ""
