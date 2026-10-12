"""Report orchestrator (M6).

The ``report`` subcommand runs the same pipeline as ``scan`` and then
writes the requested files (JSON, HTML) and prints a summary line.
"""

from __future__ import annotations

from pathlib import Path

from imagedatacheck.model import ScanResult


def write_reports(
    result: ScanResult,
    *,
    json_path: str | None = None,
    html_path: str | None = None,
    thumbnails: int = 50,
) -> dict[str, Path]:
    """Write JSON and HTML reports to the given paths (if given).

    Returns a dict mapping ``"json"``/``"html"`` to the resolved :class:`Path`
    for each file that was actually written.
    """
    from imagedatacheck.reporters.html_report import write as write_html
    from imagedatacheck.reporters.json_report import write as write_json

    written: dict[str, Path] = {}
    if json_path:
        written["json"] = write_json(result, json_path)
    if html_path:
        written["html"] = write_html(result, html_path, thumbnails=thumbnails)
    return written


__all__ = ["write_reports"]
