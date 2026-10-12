"""Standalone HTML reporter (M6).

Generates a single self-contained HTML file with:

* embedded CSS (no external ``<link>`` or ``<script src>``);
* embedded base64 thumbnails (up to ``--thumbnails``, default 50, size-capped);
* autoescape on for all Jinja2 output so hostile filenames (``<script>.jpg``)
  are escaped, never executed.

The output has no external requests and works offline.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image

from imagedatacheck.model import ScanResult

#: Max dimension (px) of an embedded thumbnail on the longest side.
_THUMB_MAX_PX = 96
#: Max bytes for a single embedded thumbnail (base64 decoded); skip the
# thumbnail entirely if the image is too large to fit under the cap.
_THUMB_MAX_BYTES = 32 * 1024


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _make_thumbnail_data_uri(path: str) -> str | None:
    """Return a base64 data URI for a thumbnail of ``path`` or ``None`` if
    the thumbnail is too big or unreadable."""
    try:
        with Image.open(path) as img:
            img.thumbnail((_THUMB_MAX_PX, _THUMB_MAX_PX))
            buf = BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=70)
        data = buf.getvalue()
        if len(data) > _THUMB_MAX_BYTES:
            return None
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:  # noqa: BLE001 - any failure -> no thumbnail
        return None


def _env() -> Environment:
    # ``autoescape=True`` enables escaping for all templates loaded here
    # (the template file has a ``.j2`` extension, which would otherwise
    # not be matched by ``select_autoescape``'s default extension list).
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    return env


def render(result: ScanResult, *, thumbnails: int = 50) -> str:
    """Render the scan result as a standalone HTML string.

    ``thumbnails`` is the maximum number of finding thumbnails to embed.
    Pass ``0`` to skip thumbnails entirely.
    """
    env = _env()
    template = env.get_template("report.html.j2")

    # Build the per-finding data; only embed a thumbnail for findings
    # that have a single file (multi-file findings get a "(N files)" label).
    findings_for_template = []
    embedded = 0
    for f in result.findings:
        thumb = None
        if thumbnails > 0 and embedded < thumbnails and len(f.files) == 1:
            thumb = _make_thumbnail_data_uri(f.files[0])
            if thumb is not None:
                embedded += 1
        findings_for_template.append(
            {
                "code": f.code,
                "severity": f.severity.value,
                "message": f.message,
                "files": list(f.files),
                "thumbnail": thumb,
            }
        )

    counts: dict[str, int] = {}
    for f in result.findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1

    return template.render(
        result=result,
        files_count=len(result.files),
        findings_count=len(result.findings),
        counts=counts,
        findings=findings_for_template,
        schema_version=result.to_dict().get("schema_version", 1),
    )


def write(result: ScanResult, path: str | Path, *, thumbnails: int = 50) -> Path:
    """Write the HTML report to ``path`` and return the resolved path."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(result, thumbnails=thumbnails), encoding="utf-8")
    return p


__all__ = ["render", "write"]
