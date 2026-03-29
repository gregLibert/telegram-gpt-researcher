"""Table-driven tests for download basename sanitization."""

from __future__ import annotations

import pytest

from bot.filename_sanitize import sanitize_download_basename


@pytest.mark.parametrize(
    ("value", "max_len", "expected"),
    [
        ("hello world", 48, "hello_world"),
        ("  foo  bar  ", 48, "foo_bar"),
        ("a/b\\c", 48, "abc"),
        ("", 48, "research"),
        ("!!!", 48, "research"),
        ("café-rapport", 48, "café-rapport"),
        ("abcdefghijklmnop", 8, "abcdefgh"),
    ],
)
def test_sanitize_download_basename(value: str, max_len: int, expected: str) -> None:
    assert sanitize_download_basename(value, max_len=max_len) == expected
