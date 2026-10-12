"""Typer CLI entry point for imagedatacheck.

This module exposes the single Typer ``app`` that is the package's CLI surface.
Only ``--version`` and the command stubs needed for M1 wiring are present.
Real commands are added in later milestones.
"""

from __future__ import annotations

import typer

from imagedatacheck import __version__

app = typer.Typer(
    name="imagedatacheck",
    help="Scan an image dataset for corrupt files, duplicates, imbalance, leakage and conflicting labels.",
    no_args_is_help=True,
    add_completion=False,
)


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


@app.command()
def scan(
    path: str = typer.Argument(..., help="Path to the image dataset root."),
) -> None:
    """Scan a dataset and print a summary to the terminal. (Stub: full implementation in M2+)"""
    typer.echo(f"scan: {path} (stub - implemented in M2)")


@app.command()
def report(
    path: str = typer.Argument(..., help="Path to the image dataset root."),
) -> None:
    """Generate a JSON and HTML report. (Stub: full implementation in M6)"""
    typer.echo(f"report: {path} (stub - implemented in M6)")
