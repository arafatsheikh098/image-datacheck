"""Tests for the package version single source of truth."""

from __future__ import annotations

import imagedatacheck


def test_version_is_nonempty_string() -> None:
    assert isinstance(imagedatacheck.__version__, str)
    assert imagedatacheck.__version__ != ""
