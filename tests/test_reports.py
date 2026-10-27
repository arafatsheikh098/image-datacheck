"""Tests for the M6 reports package."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from imagedatacheck.cli import app
from imagedatacheck.exitcodes import compute_exit_code
from imagedatacheck.model import FailureOn, Finding, ScanResult, Severity
from imagedatacheck.reporters.html_report import render as render_html
from imagedatacheck.reporters.json_report import render as render_json

# -------- Helpers --------


def _write_photo(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (64, 64))
    px = img.load()
    for i in range(64):
        for j in range(64):
            v = (color[0] + i + j) % 256
            px[i, j] = (v, color[1], color[2])
    img.save(path, format="JPEG", quality=90)


def _build_minimal_result(tmp_path: Path, *, with_finding: bool = False) -> ScanResult:
    root = tmp_path / "ds"
    _write_photo(root / "train" / "cat" / "a.jpg", (50, 100, 200))
    _write_photo(root / "train" / "cat" / "b.jpg", (150, 100, 50))
    findings: list[Finding] = []
    if with_finding:
        findings.append(
            Finding(
                code="W_IMBALANCE",
                severity=Severity.WARNING,
                message="test finding",
                files=[],
                extra={"ratio": 5.0},
            )
        )
    from imagedatacheck.layout import detect_layout
    from imagedatacheck.scanner import make_scan_result, walk

    layout, _ = detect_layout(root)
    files, _ = walk(root, layout=layout)
    return make_scan_result(root, layout, files, findings)


# -------- JSON reporter --------


def test_json_has_schema_version(tmp_path: Path) -> None:
    result = _build_minimal_result(tmp_path)
    payload = json.loads(render_json(result))
    assert payload["schema_version"] == 1
    assert payload["layout"] in {"class_folders", "split_class_folders", "flat"}


def test_json_is_deterministic(tmp_path: Path) -> None:
    result = _build_minimal_result(tmp_path, with_finding=True)
    s1 = render_json(result)
    s2 = render_json(result)
    assert s1 == s2


def test_json_finding_has_required_keys(tmp_path: Path) -> None:
    result = _build_minimal_result(tmp_path, with_finding=True)
    payload = json.loads(render_json(result))
    f = payload["findings"][0]
    assert f["code"] == "W_IMBALANCE"
    assert f["severity"] == "warning"
    assert "message" in f
    assert "files" in f
    assert "extra" in f


def test_json_no_timestamps(tmp_path: Path) -> None:
    result = _build_minimal_result(tmp_path, with_finding=True)
    text = render_json(result)
    # No "generated_at" or "timestamp" or "date" key allowed (case-sensitive)
    for token in ("generated_at", "timestamp", "date"):
        assert f'"{token}"' not in text, f"unexpected timestamp token: {token}"


# -------- HTML reporter --------


def test_html_escapes_hostile_filename(tmp_path: Path) -> None:
    """A filename like ``<script>.jpg`` must be HTML-escaped, never executed."""
    bad_name = "<script>alert(1)</script>.jpg"
    if os.name == "nt":
        from imagedatacheck.model import FileInfo, Layout

        f = FileInfo(
            path=f"C:\\demo\\{bad_name}",
            rel_path=f"demo/{bad_name}",
            size=1024,
            split="train",
            label="cat",
        )
        finding = Finding(
            code="W_DEMO",
            severity=Severity.WARNING,
            message="Hostile filename test",
            files=[f.path],
        )
        result = ScanResult(
            root="C:\\demo",
            layout=Layout.SPLIT_CLASS_FOLDERS,
            files=[f],
            findings=[finding],
        )
        html = render_html(result)
        assert "<script>alert" not in html
        assert "&lt;script&gt;alert" in html
        return

    root = tmp_path / "escape"
    p = root / "train" / "cat" / bad_name
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (10, 20, 30)).save(p, format="JPEG", quality=85)
    (root / "train" / "cat" / "x.jpg").parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (10, 20, 30)).save(
        root / "train" / "cat" / "x.jpg", format="JPEG", quality=85
    )
    (root / "train" / "dog").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (50, 60, 70)).save(
        root / "train" / "dog" / "y.jpg", format="JPEG", quality=85
    )

    from imagedatacheck.layout import detect_layout
    from imagedatacheck.scanner import make_scan_result, walk

    layout, _ = detect_layout(root)
    files, _ = walk(root, layout=layout)
    # Add a finding that mentions the hostile path so it gets rendered.
    findings = [
        Finding(
            code="W_DEMO",
            severity=Severity.WARNING,
            message="Hostile filename test",
            files=[str(p)],
        )
    ]
    result = make_scan_result(root, layout, files, findings)
    html = render_html(result)
    # Script tags must be escaped
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_html_no_external_requests(tmp_path: Path) -> None:
    """No <link href="http...">, no <script src="http...">, no http(s) URLs in src/href."""
    result = _build_minimal_result(tmp_path)
    html = render_html(result)
    # No absolute external links
    for pat in (
        r'<link[^>]+href=["\']https?://',
        r'<script[^>]+src=["\']https?://',
        r'<img[^>]+src=["\']https?://',
    ):
        assert re.search(pat, html) is None, f"external ref found: {pat}"


def test_html_thumbnails_zero_disables_thumbnails(tmp_path: Path) -> None:
    """With --thumbnails 0, no embedded base64 thumbnails."""
    result = _build_minimal_result(tmp_path, with_finding=True)
    html = render_html(result, thumbnails=0)
    # No data: URIs in this fixture's HTML
    assert "data:image/jpeg;base64" not in html


def test_html_self_contained(tmp_path: Path) -> None:
    """HTML contains inline CSS and JS, no <script src=> or <link rel=stylesheet href=...>."""
    result = _build_minimal_result(tmp_path, with_finding=True)
    html = render_html(result)
    assert "<style>" in html
    assert "<link" not in html
    assert 'src="http' not in html


# -------- Exit codes --------


def test_exit_code_clean():
    assert compute_exit_code([], FailureOn.ERROR) == 0
    assert compute_exit_code([], FailureOn.WARNING) == 0
    assert compute_exit_code([], FailureOn.NEVER) == 0


def test_exit_code_warning_triggers_warning_fail_on():
    findings = [Finding(code="X", severity=Severity.WARNING, message="w")]
    assert compute_exit_code(findings, FailureOn.WARNING) == 1
    assert compute_exit_code(findings, FailureOn.ERROR) == 0
    assert compute_exit_code(findings, FailureOn.NEVER) == 0


def test_exit_code_error_triggers_error_fail_on():
    findings = [Finding(code="X", severity=Severity.ERROR, message="e")]
    assert compute_exit_code(findings, FailureOn.ERROR) == 1
    assert compute_exit_code(findings, FailureOn.WARNING) == 1


def test_exit_code_runtime_error_overrides_fail_on():
    """E_EMPTY / E_ROOT_MISSING / etc. always return 2."""
    findings = [Finding(code="E_EMPTY", severity=Severity.ERROR, message="empty")]
    assert compute_exit_code(findings, FailureOn.NEVER) == 2
    assert compute_exit_code(findings, FailureOn.ERROR) == 2
    assert compute_exit_code(findings, FailureOn.WARNING) == 2


# -------- CLI integration --------


def test_scan_summary_prints_layout_files_findings(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_photo(root / "train" / "cat" / "a.jpg", (50, 100, 200))
    _write_photo(root / "train" / "cat" / "b.jpg", (150, 100, 50))
    _write_photo(root / "train" / "dog" / "c.jpg", (50, 150, 100))

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["scan", str(root), "--quiet", "--layout", "class_folders"],
    )
    assert result.exit_code == 0
    assert "Layout:" in result.output
    assert "Files:" in result.output
    assert "Findings:" in result.output


def test_report_subcommand_writes_html_and_json(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    _write_photo(root / "train" / "cat" / "a.jpg", (50, 100, 200))
    _write_photo(root / "train" / "cat" / "b.jpg", (150, 100, 50))
    _write_photo(root / "train" / "dog" / "c.jpg", (50, 150, 100))

    html_out = tmp_path / "report.html"
    json_out = tmp_path / "report.json"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "report",
            str(root),
            "--layout",
            "class_folders",
            "--quiet",
            "--html",
            str(html_out),
            "--json",
            str(json_out),
            "--thumbnails",
            "0",
        ],
    )
    assert result.exit_code == 0
    assert html_out.exists()
    assert json_out.exists()
    payload = json.loads(json_out.read_text())
    assert payload["schema_version"] == 1


def test_report_with_failing_finding_exits_1(tmp_path: Path) -> None:
    """An error finding triggers exit code 1 with --fail-on error."""
    root = tmp_path / "ds"
    # Corrupt file
    (root / "train" / "cat").mkdir(parents=True, exist_ok=True)
    (root / "train" / "cat" / "corrupt.jpg").write_bytes(b"not an image")
    _write_photo(root / "train" / "cat" / "ok.jpg", (50, 100, 200))
    _write_photo(root / "train" / "dog" / "x.jpg", (150, 100, 50))

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["report", str(root), "--layout", "class_folders", "--quiet"],
    )
    assert result.exit_code == 1


def test_report_with_fail_on_never_always_exits_0(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    (root / "train" / "cat").mkdir(parents=True, exist_ok=True)
    (root / "train" / "cat" / "corrupt.jpg").write_bytes(b"not an image")
    _write_photo(root / "train" / "cat" / "ok.jpg", (50, 100, 200))
    _write_photo(root / "train" / "dog" / "x.jpg", (150, 100, 50))

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "report",
            str(root),
            "--layout",
            "class_folders",
            "--quiet",
            "--fail-on",
            "never",
        ],
    )
    assert result.exit_code == 0


def test_report_empty_dir_exits_2(tmp_path: Path) -> None:
    """An empty dataset triggers E_EMPTY -> exit 2 regardless of --fail-on."""
    root = tmp_path / "empty"
    root.mkdir()
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "report",
            str(root),
            "--layout",
            "class_folders",
            "--quiet",
            "--fail-on",
            "never",
        ],
    )
    assert result.exit_code == 2
