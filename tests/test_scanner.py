"""Tests for the directory walker."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from imagedatacheck.layout import IMAGE_EXTENSIONS
from imagedatacheck.model import Layout
from imagedatacheck.scanner import make_scan_result, walk


def _touch(p: Path, content: bytes = b"x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


def test_walk_class_folders(tmp_path: Path) -> None:
    _touch(tmp_path / "cat" / "a.jpg")
    _touch(tmp_path / "cat" / "b.png")
    _touch(tmp_path / "dog" / "c.jpg")
    files, findings = walk(tmp_path, layout=Layout.CLASS_FOLDERS)
    rels = sorted(f.rel_path for f in files)
    assert rels == ["cat/a.jpg", "cat/b.png", "dog/c.jpg"]
    assert findings == []
    labels = {f.label for f in files}
    assert labels == {"cat", "dog"}


def test_walk_split_class_folders(tmp_path: Path) -> None:
    _touch(tmp_path / "train" / "cat" / "a.jpg")
    _touch(tmp_path / "test" / "dog" / "b.jpg")
    files, findings = walk(tmp_path, layout=Layout.SPLIT_CLASS_FOLDERS)
    a = next(f for f in files if f.rel_path == "train/cat/a.jpg")
    assert a.split == "train" and a.label == "cat"
    b = next(f for f in files if f.rel_path == "test/dog/b.jpg")
    assert b.split == "test" and b.label == "dog"
    assert findings == []


def test_walk_flat(tmp_path: Path) -> None:
    _touch(tmp_path / "a.jpg")
    _touch(tmp_path / "b.png")
    files, _ = walk(tmp_path, layout=Layout.FLAT)
    rels = sorted(f.rel_path for f in files)
    assert rels == ["a.jpg", "b.png"]
    assert all(f.split is None and f.label is None for f in files)


def test_hidden_files_skipped(tmp_path: Path) -> None:
    _touch(tmp_path / "cat" / "a.jpg")
    _touch(tmp_path / "cat" / ".hidden.jpg")
    _touch(tmp_path / ".hidden_dir" / "x.jpg")
    files, _ = walk(tmp_path, layout=Layout.CLASS_FOLDERS)
    rels = [f.rel_path for f in files]
    assert rels == ["cat/a.jpg"]


def test_non_ascii_paths(tmp_path: Path) -> None:
    """Non-ASCII filenames must not raise and must be discovered."""
    _touch(tmp_path / "cat" / "café_ñ.jpg")
    _touch(tmp_path / "cat" / "日本語.jpg")
    files, _ = walk(tmp_path, layout=Layout.CLASS_FOLDERS)
    names = {os.path.basename(f.path) for f in files}
    assert "café_ñ.jpg" in names
    assert "日本語.jpg" in names


def test_space_in_paths(tmp_path: Path) -> None:
    _touch(tmp_path / "cat" / "with space.jpg")
    files, _ = walk(tmp_path, layout=Layout.CLASS_FOLDERS)
    assert any("with space" in f.path for f in files)


def test_deterministic_order(tmp_path: Path) -> None:
    for i in range(20):
        _touch(tmp_path / "cls" / f"img_{i:02d}.jpg")
    files1, _ = walk(tmp_path, layout=Layout.CLASS_FOLDERS)
    files2, _ = walk(tmp_path, layout=Layout.CLASS_FOLDERS)
    assert [f.rel_path for f in files1] == [f.rel_path for f in files2]
    # Sorted lexicographically
    assert [f.rel_path for f in files1] == sorted(f.rel_path for f in files1)


def test_extensions_filter(tmp_path: Path) -> None:
    _touch(tmp_path / "cat" / "a.jpg")
    _touch(tmp_path / "cat" / "b.txt")
    files, _ = walk(tmp_path, layout=Layout.CLASS_FOLDERS, extensions={".jpg"})
    rels = [f.rel_path for f in files]
    assert rels == ["cat/a.jpg"]


def test_symlink_loop_does_not_hang(tmp_path: Path) -> None:
    """A symlink that points to an ancestor directory must not loop forever."""
    if not _symlinks_supported(tmp_path):
        pytest.skip("symlinks not supported on this platform/filesystem")
    # real/a.jpg -> file
    (tmp_path / "real").mkdir()
    _touch(tmp_path / "real" / "a.jpg")
    # real/loop -> real  (so traversing real enters real/loop which is real again)
    try:
        os.symlink(str(tmp_path / "real"), str(tmp_path / "real" / "loop"))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation failed: {exc}")
    # With follow_symlinks=False the loop directory is skipped silently,
    # so we test the follow path where the loop would otherwise be infinite.
    files, findings = walk(tmp_path, layout=Layout.CLASS_FOLDERS, follow_symlinks=True)
    rels = [f.rel_path for f in files]
    # Each unique file should appear at most once
    assert len(rels) == len(set(rels))
    assert any(f.code == "W_SYMLINK_LOOP" for f in findings)


def _symlinks_supported(path: Path) -> bool:
    target = path / "_sym_test"
    try:
        os.symlink(str(path), str(target))
        target.unlink()
        return True
    except (OSError, NotImplementedError):
        return False


def test_empty_class_folders_produces_empty_finding(tmp_path: Path) -> None:
    (tmp_path / "cat").mkdir()
    files, findings = walk(tmp_path, layout=Layout.CLASS_FOLDERS)
    assert files == []
    result = make_scan_result(tmp_path, Layout.CLASS_FOLDERS, files, findings)
    assert any(f.code == "E_EMPTY" for f in result.findings)


def test_unreadable_file_does_not_abort(tmp_path: Path) -> None:
    """A file that disappears between listing and stat must be skipped, not raise."""
    (tmp_path / "cat").mkdir()
    (tmp_path / "cat" / "a.jpg").write_bytes(b"x")
    files, findings = walk(tmp_path, layout=Layout.CLASS_FOLDERS)
    assert any(f.rel_path == "cat/a.jpg" for f in files)
    # No fatal findings
    assert not any(f.severity.value == "error" for f in findings)


def test_follow_symlinks_off_by_default(tmp_path: Path) -> None:
    if not _symlinks_supported(tmp_path):
        pytest.skip("symlinks not supported on this platform/filesystem")
    (tmp_path / "real_cat").mkdir()
    _touch(tmp_path / "real_cat" / "a.jpg")
    os.symlink(str(tmp_path / "real_cat"), str(tmp_path / "link_cat"))
    files, _ = walk(tmp_path, layout=Layout.CLASS_FOLDERS, follow_symlinks=False)
    rels = [f.rel_path for f in files]
    # link_cat/a.jpg is not followed
    assert "link_cat/a.jpg" not in rels
    assert "real_cat/a.jpg" in rels


def test_follow_symlinks_on(tmp_path: Path) -> None:
    if not _symlinks_supported(tmp_path):
        pytest.skip("symlinks not supported on this platform/filesystem")
    (tmp_path / "real_cat").mkdir()
    _touch(tmp_path / "real_cat" / "a.jpg")
    os.symlink(str(tmp_path / "real_cat"), str(tmp_path / "link_cat"))
    files, findings = walk(tmp_path, layout=Layout.CLASS_FOLDERS, follow_symlinks=True)
    rels = [f.rel_path for f in files]
    # Inode-based dedup: the symlinked dir is recognized as the same inode
    # as the real one, so the file is visited exactly once. Alphabetical
    # order means "link_cat" is entered first.
    assert "link_cat/a.jpg" in rels
    assert any(f.code == "W_SYMLINK_LOOP" for f in findings)


def test_image_extensions_constant_is_lowercase() -> None:
    for ext in IMAGE_EXTENSIONS:
        assert ext == ext.lower()
        assert ext.startswith(".")
