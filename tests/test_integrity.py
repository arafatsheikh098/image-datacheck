"""Tests for per-file integrity checks."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from imagedatacheck.integrity import check_file_integrity, run_integrity_checks


def _save_png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (96, 96)) -> None:
    Image.new("RGB", size, color).save(path, format="PNG")


def _save_jpeg(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (96, 96)) -> None:
    Image.new("RGB", size, color).save(path, format="JPEG")


def test_clean_image_no_errors(tmp_path: Path) -> None:
    p = tmp_path / "good.png"
    _save_png(p, (10, 20, 30))
    result = check_file_integrity(str(p))
    codes = {f.code for f in result.findings}
    assert "E_TRUNCATED" not in codes
    assert "E_ZERO_BYTE" not in codes
    assert "E_UNREADABLE" not in codes
    assert result.width == 96 and result.height == 96


def test_zero_byte(tmp_path: Path) -> None:
    p = tmp_path / "zero.jpg"
    p.write_bytes(b"")
    result = check_file_integrity(str(p))
    assert any(f.code == "E_ZERO_BYTE" for f in result.findings)


def test_truncated_image(tmp_path: Path) -> None:
    """A JPEG that is missing trailing bytes is detected as truncated."""
    p = tmp_path / "trunc.jpg"
    _save_jpeg(p, (200, 100, 50))
    # Truncate the file
    full = p.read_bytes()
    p.write_bytes(full[: max(1, len(full) // 2)])
    result = check_file_integrity(str(p))
    codes = {f.code for f in result.findings}
    assert "E_TRUNCATED" in codes or "E_UNREADABLE" in codes


def test_tiny_image(tmp_path: Path) -> None:
    p = tmp_path / "tiny.png"
    _save_png(p, (10, 20, 30), size=(16, 16))
    result = check_file_integrity(str(p), min_size=32)
    assert any(f.code == "E_TOO_SMALL" for f in result.findings)


def test_wrong_extension(tmp_path: Path) -> None:
    p = tmp_path / "wrong.jpg"
    # Write PNG bytes
    Image.new("RGB", (96, 96), (50, 50, 50)).save(p, format="PNG")
    result = check_file_integrity(str(p))
    assert any(f.code == "E_WRONG_EXTENSION" for f in result.findings)


def test_cmyk_info(tmp_path: Path) -> None:
    p = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (96, 96), (10, 20, 30, 40)).save(p, format="JPEG")
    result = check_file_integrity(str(p))
    assert any(f.code == "I_CMYK" for f in result.findings)
    # CMYK must be info, not error
    assert not any(f.code == "I_CMYK" and f.severity.value == "error" for f in result.findings)


def test_palette_transparency_info(tmp_path: Path) -> None:
    p = tmp_path / "pal.png"
    img = Image.new("P", (96, 96), 0)
    img.save(p, format="PNG", transparency=0)
    result = check_file_integrity(str(p))
    assert any(f.code == "I_PALETTE_TRANSPARENCY" for f in result.findings)


def test_exif_orientation_info(tmp_path: Path) -> None:
    """A JPEG with an EXIF orientation tag must be reported as info, not error."""
    from PIL.ExifTags import Base as ExifBase

    p = tmp_path / "exif.jpg"
    img = Image.new("RGB", (96, 96), (10, 10, 10))
    exif = img.getexif()
    exif[ExifBase.Orientation] = 6
    img.save(p, format="JPEG", exif=exif.tobytes())
    result = check_file_integrity(str(p))
    assert any(f.code == "I_EXIF_ORIENTATION" for f in result.findings)


def test_low_information_solid(tmp_path: Path) -> None:
    p = tmp_path / "solid.png"
    Image.new("RGB", (96, 96), (0, 0, 0)).save(p, format="PNG")
    result = check_file_integrity(str(p))
    assert result.is_low_info is True
    assert any(f.code == "W_LOW_INFORMATION" for f in result.findings)


def test_low_information_two_colors(tmp_path: Path) -> None:
    """Histogram with 2 non-empty bins counts as low information."""
    p = tmp_path / "twocolor.png"
    img = Image.new("RGB", (96, 96), (10, 20, 30))
    px = img.load()
    for x in range(96):
        for y in range(96):
            if (x + y) % 2:
                px[x, y] = (200, 100, 50)
    img.save(p, format="PNG")
    result = check_file_integrity(str(p))
    assert result.is_low_info is True


def test_decompression_bomb(tmp_path: Path) -> None:
    """A tiny file that claims a giant size is refused by Pillow's guard."""
    from PIL import Image as PILImage

    old = PILImage.MAX_IMAGE_PIXELS
    PILImage.MAX_IMAGE_PIXELS = 100  # 100 pixels
    try:
        p = tmp_path / "bomb.png"
        # 11x11 = 121 pixels > 100 -> Pillow warns/errors on open
        Image.new("RGB", (11, 11), (10, 20, 30)).save(p, format="PNG")
        # min_size=0 so E_TOO_SMALL does not fire
        result = check_file_integrity(str(p), min_size=0)
        codes = {f.code for f in result.findings}
        assert codes & {"E_DECOMPRESSION_BOMB", "E_TRUNCATED", "E_UNREADABLE"}
    finally:
        PILImage.MAX_IMAGE_PIXELS = old


def test_unreadable_returns_error_finding(tmp_path: Path) -> None:
    p = tmp_path / "garbage.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0not a real jpeg payload at all" + b"x" * 50)
    result = check_file_integrity(str(p))
    codes = {f.code for f in result.findings}
    assert codes & {"E_TRUNCATED", "E_UNREADABLE"}


def test_run_integrity_checks_sequential(tmp_path: Path) -> None:
    for i in range(3):
        _save_png(tmp_path / f"good_{i}.png", (10 * i, 20, 30))
    _save_png(tmp_path / "tiny.png", (0, 0, 0), size=(8, 8))
    findings = run_integrity_checks([str(p) for p in tmp_path.iterdir()], min_size=32, workers=1)
    codes = {f.code for f in findings}
    assert "E_TOO_SMALL" in codes


def test_run_integrity_checks_identical_results_parallel_vs_sequential(tmp_path: Path) -> None:
    """workers=1 and workers=4 must yield the same set of finding codes (order may differ)."""
    paths: list[str] = []
    for i in range(20):
        p = tmp_path / f"img_{i}.png"
        if i % 5 == 0:
            _save_png(p, (0, 0, 0), size=(4, 4))  # tiny + low-info
        elif i % 5 == 1:
            p.write_bytes(b"")  # zero-byte
        else:
            _save_png(p, (i * 10 % 256, 50, 100))
        paths.append(str(p))

    seq = run_integrity_checks(paths, min_size=32, workers=1)
    par = run_integrity_checks(paths, min_size=32, workers=4)
    seq_keys = sorted((f.code, f.message) for f in seq)
    par_keys = sorted((f.code, f.message) for f in par)
    # Strip filenames from the message so different orderings still compare equal
    seq_norm = sorted((c, _strip_path(m)) for c, m in seq_keys)
    par_norm = sorted((c, _strip_path(m)) for c, m in par_keys)
    assert seq_norm == par_norm


def _strip_path(msg: str) -> str:
    """Strip anything that looks like a path component from a finding message."""
    import re

    return re.sub(r": .+$", "", msg)


def test_one_bad_file_does_not_abort(tmp_path: Path) -> None:
    """If one file raises inside the worker, the others still get checked."""
    paths: list[str] = []
    for i in range(5):
        _save_png(tmp_path / f"good_{i}.png", (i * 5, 100, 50))
        paths.append(str(tmp_path / f"good_{i}.png"))
    # Add a path that points to a directory (causes stat OK but open fails)
    (tmp_path / "actually_dir.png").mkdir()
    paths.append(str(tmp_path / "actually_dir.png"))
    findings = run_integrity_checks(paths, min_size=32, workers=1)
    # At least the directory-as-file entry should produce an E_UNREADABLE / E_TRUNCATED
    codes = {f.code for f in findings}
    assert codes & {"E_UNREADABLE", "E_TRUNCATED", "E_ZERO_BYTE"}


def test_module_level_worker_picklable() -> None:
    """The _worker function must be a module-level callable for spawn."""
    import pickle

    from imagedatacheck.integrity import _worker

    pickle.dumps(_worker)  # must not raise


def test_missing_path_emits_unreadable(tmp_path: Path) -> None:
    """A non-existent path is reported as E_UNREADABLE."""
    p = tmp_path / "does_not_exist.jpg"
    result = check_file_integrity(str(p))
    assert any(f.code == "E_UNREADABLE" for f in result.findings)


def test_run_integrity_parallel_path(tmp_path: Path) -> None:
    """The run_integrity() (not run_integrity_checks()) parallel branch is exercised."""
    from imagedatacheck.integrity import run_integrity

    paths: list[str] = []
    for i in range(8):
        p = tmp_path / f"img_{i}.png"
        # Use a gradient so the image is NOT low-info
        img = Image.new("RGB", (96, 96))
        px = img.load()
        for x in range(96):
            for y in range(96):
                px[x, y] = ((x + i * 7) % 256, (y + i * 11) % 256, i * 5 % 256)
        img.save(p, format="PNG")
        paths.append(str(p))
    report = run_integrity(paths, min_size=32, workers=2)
    # No errors on clean images, none are low-info
    codes = {f["code"] for f in report.findings}
    assert "E_TOO_SMALL" not in codes
    assert report.low_info == set()


def test_run_integrity_parallel_with_low_info(tmp_path: Path) -> None:
    """Solid-black images are detected as low-info even in parallel mode."""
    from imagedatacheck.integrity import run_integrity

    p1 = tmp_path / "solid1.png"
    p2 = tmp_path / "solid2.png"
    Image.new("RGB", (96, 96), (5, 5, 5)).save(p1, format="PNG")
    Image.new("RGB", (96, 96), (5, 5, 5)).save(p2, format="PNG")
    report = run_integrity([str(p1), str(p2)], min_size=32, workers=2)
    assert str(p1) in report.low_info
    assert str(p2) in report.low_info
    # Findings are dicts in the parallel path
    codes = {f["code"] for f in report.findings}
    assert "W_LOW_INFORMATION" in codes


def test_worker_with_meta_handles_exceptions(tmp_path: Path) -> None:
    """The _worker_with_meta function survives an exception during check."""
    from imagedatacheck.integrity import _worker_with_meta

    # Non-existent path: check_file_integrity returns a finding, not an exception
    result = _worker_with_meta(str(tmp_path / "missing.jpg"), 32)
    assert "findings" in result
    assert "path" in result
    assert "low_info" in result
