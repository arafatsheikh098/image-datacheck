"""Tests for layout detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from imagedatacheck.layout import (
    SPLIT_NAMES,
    assign_label_and_split,
    detect_layout,
    is_hidden,
)
from imagedatacheck.model import Layout, Severity


def _make_class_folders(root: Path) -> None:
    for cls in ("cat", "dog"):
        (root / cls).mkdir(parents=True)
        (root / cls / f"{cls}_01.jpg").write_bytes(b"x")


def _make_split_class_folders(root: Path) -> None:
    for split in ("train", "val", "test"):
        for cls in ("cat", "dog"):
            (root / split / cls).mkdir(parents=True)
            (root / split / cls / f"{cls}_01.jpg").write_bytes(b"x")


def _make_flat(root: Path) -> None:
    (root / "a.jpg").write_bytes(b"x")
    (root / "b.png").write_bytes(b"x")


def test_detect_class_folders(tmp_path: Path) -> None:
    _make_class_folders(tmp_path)
    layout, findings = detect_layout(tmp_path)
    assert layout is Layout.CLASS_FOLDERS
    assert findings == []


def test_detect_split_class_folders(tmp_path: Path) -> None:
    _make_split_class_folders(tmp_path)
    layout, findings = detect_layout(tmp_path)
    assert layout is Layout.SPLIT_CLASS_FOLDERS
    assert findings == []


def test_detect_flat(tmp_path: Path) -> None:
    _make_flat(tmp_path)
    layout, findings = detect_layout(tmp_path)
    assert layout is Layout.FLAT
    assert findings == []


def test_ambiguous_falls_back_to_class_folders(tmp_path: Path) -> None:
    """If the root matches both class_folders and split_class_folders, prefer class_folders and warn."""
    # Class folders at the root
    (tmp_path / "cat").mkdir()
    (tmp_path / "cat" / "a.jpg").write_bytes(b"x")
    (tmp_path / "dog").mkdir()
    (tmp_path / "dog" / "a.jpg").write_bytes(b"x")
    # Two split directories (train + test) with class sub-folders
    (tmp_path / "train").mkdir()
    (tmp_path / "train" / "cat").mkdir()
    (tmp_path / "train" / "cat" / "x.jpg").write_bytes(b"x")
    (tmp_path / "train" / "dog").mkdir()
    (tmp_path / "train" / "dog" / "x.jpg").write_bytes(b"x")
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "cat").mkdir()
    (tmp_path / "test" / "cat" / "x.jpg").write_bytes(b"x")
    (tmp_path / "test" / "dog").mkdir()
    (tmp_path / "test" / "dog" / "x.jpg").write_bytes(b"x")
    layout, findings = detect_layout(tmp_path)
    assert layout is Layout.CLASS_FOLDERS
    codes = [f.code for f in findings]
    assert "W_LAYOUT_AMBIGUOUS" in codes


def test_layout_override(tmp_path: Path) -> None:
    _make_split_class_folders(tmp_path)
    layout, findings = detect_layout(tmp_path, override=Layout.FLAT)
    assert layout is Layout.FLAT
    assert findings == []


def test_missing_root(tmp_path: Path) -> None:
    layout, findings = detect_layout(tmp_path / "does-not-exist")
    assert any(f.severity is Severity.ERROR for f in findings)
    assert findings[0].code in {"E_ROOT_MISSING", "E_ROOT_NOT_DIR"}


def test_assign_label_class_folders(tmp_path: Path) -> None:
    _make_class_folders(tmp_path)
    split, label = assign_label_and_split(
        tmp_path, tmp_path / "cat" / "a.jpg", Layout.CLASS_FOLDERS
    )
    assert split is None and label == "cat"


def test_assign_label_split_class_folders(tmp_path: Path) -> None:
    _make_split_class_folders(tmp_path)
    split, label = assign_label_and_split(
        tmp_path, tmp_path / "train" / "cat" / "a.jpg", Layout.SPLIT_CLASS_FOLDERS
    )
    assert split == "train"
    assert label == "cat"


def test_assign_label_split_normalized(tmp_path: Path) -> None:
    _make_split_class_folders(tmp_path)
    split, label = assign_label_and_split(
        tmp_path, tmp_path / "validation" / "dog" / "a.jpg", Layout.SPLIT_CLASS_FOLDERS
    )
    assert split == "val"
    assert label == "dog"


def test_assign_label_flat(tmp_path: Path) -> None:
    _make_flat(tmp_path)
    split, label = assign_label_and_split(tmp_path, tmp_path / "a.jpg", Layout.FLAT)
    assert split is None and label is None


def test_is_hidden() -> None:
    assert is_hidden(Path(".hidden/file.jpg"))
    assert is_hidden(Path("a/.hidden"))
    assert not is_hidden(Path("a/b.jpg"))
    # A file literally named '.jpg' has a hidden basename
    assert is_hidden(Path("a/.jpg"))


def test_split_names_completeness() -> None:
    """All training variants must be mapped; non-split names are not in the table."""
    for raw, normalized in (
        ("train", "train"),
        ("training", "train"),
        ("val", "val"),
        ("valid", "val"),
        ("validation", "val"),
        ("test", "test"),
        ("testing", "test"),
    ):
        assert SPLIT_NAMES[raw] == normalized


@pytest.mark.parametrize("layout", list(Layout))
def test_empty_dir_layout_returns_clean(tmp_path: Path, layout: Layout) -> None:
    """An empty folder for an overridden layout does not error in detection."""
    layout, findings = detect_layout(tmp_path, override=layout)
    assert layout is layout
    # No error findings from detection itself when the layout is forced
    assert not any(f.severity is Severity.ERROR for f in findings)


def test_empty_dir_no_override_emits_error(tmp_path: Path) -> None:
    """An empty folder with no override produces an E_EMPTY error finding (exit code 2)."""
    layout, findings = detect_layout(tmp_path)
    assert any(f.code == "E_EMPTY" and f.severity is Severity.ERROR for f in findings)
