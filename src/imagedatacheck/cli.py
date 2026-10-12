"""Typer CLI entry point for imagedatacheck."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import typer
from rich.console import Console

from imagedatacheck import __version__
from imagedatacheck.integrity import run_integrity_checks
from imagedatacheck.layout import detect_layout
from imagedatacheck.model import FailureOn, Finding, Layout, Severity
from imagedatacheck.progress import make_progress
from imagedatacheck.scanner import make_scan_result, walk

app = typer.Typer(
    name="imagedatacheck",
    help="Scan an image dataset for corrupt files, duplicates, imbalance, leakage and conflicting labels.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(code=0)


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """imagedatacheck root options."""


def _compute_exit_code(findings: Sequence[Finding], fail_on: FailureOn) -> int:
    """Apply the --fail-on policy. 0 = pass, 1 = findings at or above threshold, 2 = usage/runtime error."""
    if fail_on is FailureOn.NEVER:
        return 0
    order = {Severity.ERROR: 2, Severity.WARNING: 1, Severity.INFO: 0}
    threshold = order[FailureOn_to_Severity(fail_on)]
    max_seen = 0
    for f in findings:
        sev = f.severity
        max_seen = max(max_seen, order.get(sev, 0))
    return 1 if max_seen >= threshold else 0


def FailureOn_to_Severity(value: FailureOn) -> Severity:
    if value is FailureOn.NEVER:
        return Severity.INFO  # never fail; we return early
    if value is FailureOn.ERROR:
        return Severity.ERROR
    return Severity.WARNING


def _parse_extensions(value: str) -> set[str]:
    parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    out: set[str] = set()
    for p in parts:
        if not p.startswith("."):
            p = "." + p
        out.add(p)
    if not out:
        raise typer.BadParameter("--extensions must list at least one extension")
    return out


@app.command()
def scan(
    path: str = typer.Argument(..., help="Path to the image dataset root."),
    workers: int = typer.Option(
        1, "--workers", min=1, help="Worker processes (1 disables multiprocessing)."
    ),
    layout: Layout | None = typer.Option(
        None, "--layout", help="Force a specific layout (default: auto)."
    ),
    extensions: str | None = typer.Option(
        None, "--extensions", help="Comma-separated extensions, e.g. jpg,png"
    ),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symbolic links (off by default)."
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output."),
    min_size: int = typer.Option(32, "--min-size", min=1, help="Min image width/height."),
    imbalance_ratio: float = typer.Option(
        10.0, "--imbalance-ratio", min=1.0, help="Class-imbalance threshold."
    ),
    fail_on: FailureOn = typer.Option(
        FailureOn.ERROR, "--fail-on", help="Fail level for exit code."
    ),
    _phash_threshold: int = typer.Option(
        4, "--phash-threshold", min=0, max=64, help="(M4) Hamming distance threshold."
    ),
    _rotation_invariant: bool = typer.Option(
        False, "--rotation-invariant", help="(M4) Match rotated and flipped copies."
    ),
    _no_near_duplicates: bool = typer.Option(
        False, "--no-near-duplicates", help="(M4) Skip near-duplicate detection."
    ),
) -> None:
    """Scan a dataset and print a summary to the terminal."""
    root = Path(path).resolve()
    exts = _parse_extensions(extensions) if extensions else None
    detected, findings = detect_layout(root, override=layout)
    if any(f.severity is Severity.ERROR for f in findings):
        for f in findings:
            console.print(f"[red]{f.severity.value}:[/red] {f.message}")
        raise typer.Exit(code=2)
    for f in findings:
        console.print(f"[yellow]{f.severity.value}:[/yellow] {f.message}")

    progress = make_progress(quiet)
    if progress is not None:
        with progress:
            files, walk_findings = walk(
                root,
                layout=detected,
                extensions=exts,
                follow_symlinks=follow_symlinks,
            )
    else:
        files, walk_findings = walk(
            root,
            layout=detected,
            extensions=exts,
            follow_symlinks=follow_symlinks,
        )
    findings.extend(walk_findings)

    # Integrity step (M3): run after the walk, optionally in parallel.
    if files:
        progress = make_progress(quiet)
        if progress is not None:
            with progress:
                integrity_findings = run_integrity_checks(
                    [f.path for f in files], min_size=min_size, workers=workers
                )
        else:
            integrity_findings = run_integrity_checks(
                [f.path for f in files], min_size=min_size, workers=workers
            )
        findings.extend(integrity_findings)

    result = make_scan_result(root, detected, files, findings)
    console.print(
        f"[bold]Layout:[/bold] {result.layout.value}  "
        f"[bold]Files:[/bold] {len(result.files)}  "
        f"[bold]Findings:[/bold] {len(result.findings)}"
    )
    # Empty dataset or missing path are runtime errors (exit 2), not data issues.
    if any(f.code in {"E_EMPTY", "E_ROOT_MISSING", "E_ROOT_NOT_DIR"} for f in result.findings):
        raise typer.Exit(code=2)
    raise typer.Exit(code=_compute_exit_code(result.findings, fail_on))


@app.command()
def report(
    path: str = typer.Argument(..., help="Path to the image dataset root."),
    html: str | None = typer.Option(None, "--html", help="Write HTML report to this path."),
    json: str | None = typer.Option(None, "--json", help="Write JSON report to this path."),
) -> None:
    """Generate a JSON and HTML report. (Stub: full implementation in M6)"""
    typer.echo(f"report: {path} (stub - implemented in M6)")


if __name__ == "__main__":
    app()
    sys.exit(0)  # pragma: no cover
