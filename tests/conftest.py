"""Shared fixtures for imagedatacheck tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image


def _write_photo(path: Path, color: tuple[int, int, int], size: int = 64) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use a smooth gradient so the phash is non-trivial
    img = Image.new("RGB", (size, size))
    px = img.load()
    for i in range(size):
        for j in range(size):
            v = (color[0] + i + j) % 256
            px[i, j] = (v, (color[1] + j) % 256, (color[2] + i) % 256)
    img.save(path, format="JPEG", quality=90)


@pytest.fixture
def make_photo() -> Any:
    """Factory that writes a deterministic photo-like JPEG to a path."""
    return _write_photo


@pytest.fixture
def clean_dataset(tmp_path: Path, make_photo: Any) -> Path:
    """A small clean split_class_folders dataset with no planted problems.

    Layout::

        train/
            cat/  3 images
            dog/  3 images
        val/
            cat/  1 image
            dog/  1 image
    """
    root = tmp_path / "clean"
    for split, counts in [("train", {"cat": 3, "dog": 3}), ("val", {"cat": 1, "dog": 1})]:
        for cls, n in counts.items():
            for i in range(n):
                make_photo(
                    root / split / cls / f"{cls}_{i:02d}.jpg",
                    color=(50 + i * 30, 100, 150),
                )
    return root
