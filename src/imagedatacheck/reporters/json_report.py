"""JSON reporter (M6).

Outputs a deterministic, byte-stable JSON document. The shape is
documented in ``docs/json_schema.md`` and carries a top-level
``schema_version`` so downstream consumers can guard against breakage.

Determinism
-----------
* Keys are emitted in a fixed order (Python 3.7+ dict preserves
  insertion order; we always insert in the documented order).
* ``json.dumps(..., sort_keys=True, indent=2)`` is used for the
  canonical form, so two equal inputs always produce byte-identical
  output.
* No timestamps are emitted in the canonical form. The CLI may add a
  ``generated_at`` field, but only when the caller asks for it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from imagedatacheck.model import SCHEMA_VERSION, ScanResult


def render(result: ScanResult, *, indent: int = 2) -> str:
    """Render the scan result as a deterministic JSON string."""
    payload = result.to_dict()
    return json.dumps(payload, sort_keys=True, indent=indent, ensure_ascii=False)


def write(result: ScanResult, path: str | Path, *, indent: int = 2) -> Path:
    """Write the JSON report to ``path`` and return the resolved path."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(result, indent=indent) + "\n", encoding="utf-8")
    return p


__all__ = ["render", "write", "SCHEMA_VERSION"]
_ = Any  # type-check-only import marker; keeps mypy happy in some versions
