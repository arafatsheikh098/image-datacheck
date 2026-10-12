"""CLI tests for M2: scan with layout / extensions / quiet / missing path."""

from __future__ import annotations

import subprocess
import sys

from typer.testing import CliRunner

from imagedatacheck.cli import app


def test_scan_class_folders(tmp_path) -> None:
    (tmp_path / "cat").mkdir()
    (tmp_path / "cat" / "a.jpg").write_bytes(b"x")
    (tmp_path / "dog").mkdir()
    (tmp_path / "dog" / "b.jpg").write_bytes(b"x")
    runner = CliRunner()
    result = runner.invoke(app, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "class_folders" in result.output or "Files:" in result.output


def test_scan_missing_path_exits_2(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["scan", str(tmp_path / "nope")])
    assert result.exit_code == 2


def test_scan_empty_dir_exits_2(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["scan", str(tmp_path)])
    assert result.exit_code == 2


def test_scan_layout_override(tmp_path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    runner = CliRunner()
    result = runner.invoke(app, ["scan", str(tmp_path), "--layout", "flat"])
    assert result.exit_code == 0
    assert "flat" in result.output


def test_scan_quiet(tmp_path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    runner = CliRunner()
    result = runner.invoke(app, ["scan", str(tmp_path), "--layout", "flat", "--quiet"])
    assert result.exit_code == 0
    assert "Files:" in result.output


def test_scan_extensions(tmp_path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.png").write_bytes(b"x")
    (tmp_path / "c.gif").write_bytes(b"x")
    runner = CliRunner()
    result = runner.invoke(
        app, ["scan", str(tmp_path), "--layout", "flat", "--extensions", "jpg,png"]
    )
    assert result.exit_code == 0
    assert "Files: 2" in result.output


def test_scan_via_python_module(tmp_path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    completed = subprocess.run(
        [sys.executable, "-m", "imagedatacheck", "scan", str(tmp_path), "--layout", "flat"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "Files: 1" in completed.stdout
