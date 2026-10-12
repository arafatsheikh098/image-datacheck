"""Typer CLI entry point for imagedatacheck."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from imagedatacheck import __version__
from imagedatacheck.dataset import run_dataset_checks
from imagedatacheck.duplicates import (
    DuplicateGroup,
    find_exact_duplicates,
    find_near_duplicates,
)
from imagedatacheck.exitcodes import compute_exit_code
from imagedatacheck.integrity import run_integrity
from imagedatacheck.layout import detect_layout
from imagedatacheck.model import FailureOn, FileInfo, Finding, Layout, Severity
from imagedatacheck.progress import make_progress
from imagedatacheck.report import write_reports
from imagedatacheck.reporters.rich_summary import render as render_summary
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


def _run_pipeline(
    root: Path,
    *,
    layout: Layout | None,
    extensions: str | None,
    follow_symlinks: bool,
    min_size: int,
    imbalance_ratio: float,
    phash_threshold: int,
    rotation_invariant: bool,
    no_near_duplicates: bool,
    workers: int,
    quiet: bool,
) -> tuple[Layout, list[FileInfo], list[Finding]]:
    """Run the full scan pipeline and return (layout, files, findings).

    Shared by ``scan`` and ``report`` so the data-collection logic is not
    duplicated.
    """
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

    # Integrity step (M3)
    low_info: set[str] = set()
    if files:
        progress = make_progress(quiet)
        if progress is not None:
            with progress:
                report_int = run_integrity(
                    [f.path for f in files], min_size=min_size, workers=workers
                )
        else:
            report_int = run_integrity([f.path for f in files], min_size=min_size, workers=workers)
        findings.extend(report_int.findings)
        low_info = report_int.low_info

    # Duplicates step (M4)
    all_duplicates: list[DuplicateGroup] = []
    if files and not no_near_duplicates:
        file_paths = [f.path for f in files]
        progress = make_progress(quiet)
        if progress is not None:
            with progress:
                exact = find_exact_duplicates(file_paths)
                near = find_near_duplicates(
                    file_paths,
                    threshold=phash_threshold,
                    rotation_invariant=rotation_invariant,
                    low_info_paths=low_info,
                )
        else:
            exact = find_exact_duplicates(file_paths)
            near = find_near_duplicates(
                file_paths,
                threshold=phash_threshold,
                rotation_invariant=rotation_invariant,
                low_info_paths=low_info,
            )
        all_duplicates = list(exact) + list(near)
        for g in exact:
            findings.append(
                Finding(
                    code="W_EXACT_DUPLICATE",
                    severity=Severity.WARNING,
                    message=f"Exact duplicate group {g.group_id} has {len(g.members)} members.",
                    files=list(g.members),
                    extra={"group_id": g.group_id, "kind": "exact"},
                )
            )
        for g in near:
            findings.append(
                Finding(
                    code="W_NEAR_DUPLICATE",
                    severity=Severity.WARNING,
                    message=f"Near-duplicate group {g.group_id} has {len(g.members)} members.",
                    files=list(g.members),
                    extra={"group_id": g.group_id, "kind": "near"},
                )
            )

    # Dataset-level checks (M5)
    if files:
        findings.extend(run_dataset_checks(files, all_duplicates, imbalance_ratio=imbalance_ratio))

    return detected, files, findings


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
    detected, files, findings = _run_pipeline(
        root,
        layout=layout,
        extensions=extensions,
        follow_symlinks=follow_symlinks,
        min_size=min_size,
        imbalance_ratio=imbalance_ratio,
        phash_threshold=_phash_threshold,
        rotation_invariant=_rotation_invariant,
        no_near_duplicates=_no_near_duplicates,
        workers=workers,
        quiet=quiet,
    )
    result = make_scan_result(root, detected, files, findings)
    render_summary(result, console=console)
    raise typer.Exit(code=compute_exit_code(result.findings, fail_on))


@app.command()
def report(
    path: str = typer.Argument(..., help="Path to the image dataset root."),
    html: str | None = typer.Option(None, "--html", help="Write HTML report to this path."),
    json: str | None = typer.Option(None, "--json", help="Write JSON report to this path."),
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
    thumbnails: int = typer.Option(
        50, "--thumbnails", min=0, help="Max number of embedded HTML thumbnails (0 disables)."
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
    """Run the scan and write JSON/HTML reports."""
    root = Path(path).resolve()
    detected, files, findings = _run_pipeline(
        root,
        layout=layout,
        extensions=extensions,
        follow_symlinks=follow_symlinks,
        min_size=min_size,
        imbalance_ratio=imbalance_ratio,
        phash_threshold=_phash_threshold,
        rotation_invariant=_rotation_invariant,
        no_near_duplicates=_no_near_duplicates,
        workers=workers,
        quiet=quiet,
    )
    result = make_scan_result(root, detected, files, findings)
    written = write_reports(result, json_path=json, html_path=html, thumbnails=thumbnails)
    render_summary(result, console=console)
    for kind, p in written.items():
        console.print(f"[green]Wrote[/green] {kind}: {p}")
    raise typer.Exit(code=compute_exit_code(result.findings, fail_on))


if __name__ == "__main__":
    app()
    sys.exit(0)  # pragma: no cover
