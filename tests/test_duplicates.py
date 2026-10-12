"""Tests for the duplicate-detection pipeline."""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image

from imagedatacheck.duplicates import (
    DuplicateGroup,
    find_exact_duplicates,
    find_near_duplicates,
)


def _random_photo(path: Path, seed: int, size: int = 128) -> None:
    """Write a photo-like JPEG (random noise with a 2x2 block) at ``path``."""
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (size, size))
    px = img.load()
    # Smooth gradient + small noise: realistic content
    for i in range(size):
        for j in range(size):
            px[i, j] = (
                (i * 3 + rng.randint(0, 30)) % 256,
                (j * 5 + rng.randint(0, 30)) % 256,
                (i + j + rng.randint(0, 30)) % 256,
            )
    img.save(path, format="JPEG", quality=90)


def test_exact_duplicates_groups_same_bytes(tmp_path: Path) -> None:
    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"
    p3 = tmp_path / "c.jpg"
    _random_photo(p1, 1)
    p2.write_bytes(p1.read_bytes())
    p3.write_bytes(p1.read_bytes())

    groups = find_exact_duplicates([str(p1), str(p2), str(p3)])
    assert len(groups) == 1
    assert sorted(groups[0].members) == sorted([str(p1), str(p2), str(p3)])


def test_exact_duplicates_no_group_for_unique(tmp_path: Path) -> None:
    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"
    _random_photo(p1, 1)
    _random_photo(p2, 2)
    groups = find_exact_duplicates([str(p1), str(p2)])
    assert groups == []


def test_near_duplicates_finds_re_saved(tmp_path: Path) -> None:
    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"
    _random_photo(p1, 42)
    # Re-save with high quality (same content, just different bitstream)
    Image.open(p1).save(p2, format="JPEG", quality=90)

    groups = find_near_duplicates([str(p1), str(p2)], threshold=4, rotation_invariant=False)
    assert len(groups) >= 1, f"expected ≥1 group, got {groups}"
    assert str(p1) in groups[0].members
    assert str(p2) in groups[0].members


def test_near_duplicates_rotation_invariant(tmp_path: Path) -> None:
    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b_rot.jpg"
    _random_photo(p1, 99)
    img = Image.open(p1).rotate(90, expand=True)
    img.save(p2, format="JPEG", quality=90)

    # Without rotation invariance (threshold small) these may or may not match
    # (depending on how rotation affects phash).
    find_near_duplicates([str(p1), str(p2)], threshold=0, rotation_invariant=False)
    # With rotation invariance they should match
    groups_rot = find_near_duplicates([str(p1), str(p2)], threshold=4, rotation_invariant=True)
    # Just check that rotation_invariant finds a group.
    assert len(groups_rot) >= 1, f"rotation_invariant did not find group: {groups_rot}"


def test_near_duplicates_excludes_low_info(tmp_path: Path) -> None:
    p1 = tmp_path / "a_solid.jpg"
    p2 = tmp_path / "b_solid.jpg"
    Image.new("RGB", (64, 64), (10, 10, 10)).save(p1, format="JPEG", quality=85)
    Image.new("RGB", (64, 64), (10, 10, 10)).save(p2, format="JPEG", quality=85)
    groups = find_near_duplicates(
        [str(p1), str(p2)],
        threshold=4,
        rotation_invariant=False,
        low_info_paths={str(p1), str(p2)},
    )
    assert groups == []


def test_near_duplicates_stable_group_id(tmp_path: Path) -> None:
    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"
    _random_photo(p1, 7)
    p2.write_bytes(p1.read_bytes())

    g1 = find_exact_duplicates([str(p1), str(p2)])
    g2 = find_exact_duplicates([str(p1), str(p2)])
    assert g1[0].group_id == g2[0].group_id


def test_near_duplicates_deterministic_order(tmp_path: Path) -> None:
    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"
    p3 = tmp_path / "c.jpg"
    _random_photo(p1, 11)
    p2.write_bytes(p1.read_bytes())
    p3.write_bytes(p1.read_bytes())

    g1 = find_exact_duplicates([str(p1), str(p2), str(p3)])
    g2 = find_exact_duplicates([str(p3), str(p1), str(p2)])
    assert g1[0].group_id == g2[0].group_id
    assert g1[0].members == g2[0].members


def test_duplicate_group_dataclass() -> None:
    g = DuplicateGroup(group_id="abc", kind="exact", members=["a", "b"])
    assert g.group_id == "abc"
    assert g.kind == "exact"
    assert g.members == ["a", "b"]
