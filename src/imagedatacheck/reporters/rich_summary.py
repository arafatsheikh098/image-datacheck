"""Rich terminal summary (M6).

Prints a one-line layout/files/findings summary followed by a grouped
table of findings. All output is via :class:`rich.console.Console` so it
honors the ``--quiet`` flag and a non-tty environment automatically.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from rich.console import Console
from rich.table import Table

from imagedatacheck.model import Finding, ScanResult, Severity

_SEVERITY_STYLE: dict[Severity, str] = {
    Severity.ERROR: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}


def render(
    result: ScanResult,
    *,
    console: Console | None = None,
    show_table: bool = True,
) -> None:
    """Print a summary of the scan to ``console`` (default: stdout)."""
    c = console or Console()
    sev_counts = Counter(f.severity for f in result.findings)
    c.print(
        f"[bold]Layout:[/bold] {result.layout.value}  "
        f"[bold]Files:[/bold] {len(result.files)}  "
        f"[bold]Findings:[/bold] {len(result.findings)} "
        f"(error={sev_counts[Severity.ERROR]}, "
        f"warning={sev_counts[Severity.WARNING]}, "
        f"info={sev_counts[Severity.INFO]})"
    )
    if not show_table or not result.findings:
        return
    t = Table(title="Findings", show_lines=False, header_style="bold")
    t.add_column("Severity", style="bold")
    t.add_column("Code")
    t.add_column("Message", overflow="fold")
    t.add_column("Files", justify="right")
    for f in result.findings:
        t.add_row(
            f"[{_SEVERITY_STYLE[f.severity]}]{f.severity.value}[/]",
            f.code,
            f.message,
            str(len(f.files)),
        )
    c.print(t)


def render_summary_line(result: ScanResult, *, console: Console | None = None) -> None:
    """Print only the one-line summary, no table."""
    render(result, console=console, show_table=False)


def severity_counts(findings: Iterable[Finding]) -> dict[str, int]:
    """Return a dict ``{severity_name: count}`` for the given findings."""
    c: Counter[str] = Counter()
    for f in findings:
        c[f.severity.value] += 1
    return dict(c)


__all__ = ["render", "render_summary_line", "severity_counts"]
