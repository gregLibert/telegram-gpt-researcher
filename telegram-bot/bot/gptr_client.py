"""Async HTTP client for the GPT Researcher API (POST /report/)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


def _base_url() -> str:
    return os.environ.get("GPTR_API_URL", "http://gpt-researcher:8000").rstrip("/")


@dataclass(frozen=True)
class ResearchDeliveryMeta:
    """Structured metadata returned alongside the Markdown report body."""

    estimated_total_usd: float | None
    source_urls: tuple[str, ...]
    visited_urls: tuple[str, ...]
    step_costs: tuple[tuple[str, float], ...]


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_step_costs(raw: object) -> tuple[tuple[str, float], ...]:
    if not isinstance(raw, dict):
        return ()
    out: list[tuple[str, float]] = []
    for key, val in raw.items():
        if not isinstance(key, str):
            continue
        n = _coerce_float(val)
        if n is not None:
            out.append((key, n))
    return tuple(out)


def _normalize_url_list(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(str(x) for x in raw if isinstance(x, str) and x.strip())


def parse_research_delivery_meta(payload: dict[str, Any]) -> ResearchDeliveryMeta:
    """
    Extract cost and URL fields from a GPT Researcher ``/report/`` JSON object.

    Tries ``research_information`` first (upstream shape), then ``metadata`` fallbacks.
    """
    total: float | None = None
    sources: tuple[str, ...] = ()
    visited: tuple[str, ...] = ()
    steps: tuple[tuple[str, float], ...] = ()

    ri = payload.get("research_information")
    if isinstance(ri, dict):
        rc = ri.get("research_costs")
        total = _coerce_float(rc)
        if total is None and isinstance(rc, dict):
            steps = _normalize_step_costs(rc)
            if steps:
                total = sum(v for _, v in steps)
        sources = _normalize_url_list(ri.get("source_urls"))
        visited = _normalize_url_list(ri.get("visited_urls"))
        sc = ri.get("step_costs") or ri.get("research_step_costs")
        if isinstance(sc, dict) and not steps:
            steps = _normalize_step_costs(sc)

    md = payload.get("metadata")
    if isinstance(md, dict) and total is None:
        for key in ("costs", "research_costs", "total_cost", "estimated_cost_usd"):
            cand = md.get(key)
            total = _coerce_float(cand)
            if total is not None:
                break
            if isinstance(cand, dict):
                steps = _normalize_step_costs(cand)
                if steps:
                    total = sum(v for _, v in steps)
                    break
        if not sources:
            sources = _normalize_url_list(md.get("source_urls"))
        if not visited:
            visited = _normalize_url_list(md.get("visited_urls"))

    return ResearchDeliveryMeta(
        estimated_total_usd=total,
        source_urls=sources,
        visited_urls=visited,
        step_costs=steps,
    )


def format_delivery_summary(meta: ResearchDeliveryMeta) -> str:
    """
    Build a short English summary for Telegram captions (cost and URL counts).

    Omits fields that are unknown or empty.
    """
    parts: list[str] = []
    if meta.estimated_total_usd is not None:
        parts.append(f"💰 Estimated Cost: ${meta.estimated_total_usd:.4f}")
    if meta.source_urls:
        parts.append(f"📚 Sources: {len(meta.source_urls)}")
    if meta.visited_urls:
        parts.append(f"🔗 Visited URLs: {len(meta.visited_urls)}")
    return " · ".join(parts)


async def generate_report(
    task: str,
    *,
    report_type: str = "research_report",
    report_source: str = "web",
    tone: str = "Objective",
    timeout_s: float = 900.0,
) -> dict[str, Any]:
    """
    Call GPT Researcher with ``generate_in_background=false`` and return the JSON object.

    Fields mirror the upstream ``ResearchRequest`` model (see gpt-researcher backend).
    Use :func:`parse_research_delivery_meta` on the result for costs and URLs.
    """
    payload = {
        "task": task,
        "report_type": report_type,
        "report_source": report_source,
        "tone": tone,
        "headers": None,
        "repo_name": "",
        "branch_name": "",
        "generate_in_background": False,
    }
    url = f"{_base_url()}/report/"
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Invalid GPT Researcher response: expected a JSON object.")
        return data
