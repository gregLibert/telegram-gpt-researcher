"""Table-driven tests for allowlist parsing."""

from __future__ import annotations

import pytest

from bot.allowlist import parse_allowed_user_ids


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,2,3", {1, 2, 3}),
        ("1;2;3", {1, 2, 3}),
        ("1, 2 ; 3", {1, 2, 3}),
        ("  42  ", {42}),
        ("1,,2", {1, 2}),
        ("", set()),
        ("  ,  ,  ", set()),
    ],
)
def test_parse_allowed_user_ids_splits_and_strips(raw: str, expected: set[int]) -> None:
    assert parse_allowed_user_ids(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "not_a_number",
        "1,abc",
        "1.5",
    ],
)
def test_parse_allowed_user_ids_rejects_invalid_integers(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_allowed_user_ids(raw)
