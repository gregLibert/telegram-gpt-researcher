"""Async HTTP client for the GPT Researcher API (POST /report/)."""

from __future__ import annotations

import os
from typing import Any

import httpx


def _base_url() -> str:
    return os.environ.get("GPTR_API_URL", "http://gpt-researcher:8000").rstrip("/")


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
