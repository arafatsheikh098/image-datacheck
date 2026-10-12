"""Tests for the CLI entry point (M1: --version, --help, stub commands)."""

from __future__ import annotations

import re
import subprocess
import sys

from typer.testing import CliRunner

from imagedatacheck import __version__
from imagedatacheck.cli import app


def test_help_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output


def test_version_flag_prints_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_scan_stub_runs(tmp_path) -> None:
    # M2: real scan wired in. Provide a valid flat dir.
    from PIL import Image

    Image.new("RGB", (96, 96), (10, 20, 30)).save(tmp_path / "a.jpg", format="JPEG")
    runner = CliRunner()
    result = runner.invoke(app, ["scan", str(tmp_path), "--layout", "flat"])
    assert result.exit_code == 0
    assert "Files: 1" in result.output


def test_report_stub_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["report", "."])
    assert result.exit_code == 0
    assert "report" in result.stdout


def test_python_dash_m_runs() -> None:
    """``python -m imagedatacheck --version`` works (entry-point safety)."""
    completed = subprocess.run(
        [sys.executable, "-m", "imagedatacheck", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == __version__


def test_version_matches_semverish() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert re.match(r"^\d+\.\d+\.\d+", result.stdout.strip()), result.stdout
