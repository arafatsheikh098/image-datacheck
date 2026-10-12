"""Tests for the demo dataset generator."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from examples.make_demo_dataset import main as generate


def test_demo_dataset_is_deterministic(tmp_path: Path) -> None:
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    generate(str(out1))
    generate(str(out2))
    diffs: list[str] = []
    for a, b in zip(sorted(out1.rglob("*")), sorted(out2.rglob("*")), strict=False):
        if a.is_file():
            if a.read_bytes() != b.read_bytes():
                diffs.append(a.name)
    assert diffs == []


def test_demo_dataset_has_all_planted_problems(tmp_path: Path) -> None:
    out = tmp_path / "demo"
    generate(str(out))

    # 1. Corrupt file
    corrupt = out / "train" / "cat" / "corrupt.jpg"
    assert corrupt.exists()
    # Should not open as a valid image
    try:
        Image.open(corrupt).verify()
        # If verify passes, the JPEG signature bytes at the end were enough;
        # we still expect Image.open().load() to fail.
        Image.open(corrupt).load()
    except Exception:
        pass
    else:
        # If neither raised, the file is unexpectedly valid
        raise AssertionError("corrupt.jpg unexpectedly loaded as a valid image")

    # 2. Tiny image
    tiny = out / "train" / "bird" / "tiny.jpg"
    assert tiny.exists()
    with Image.open(tiny) as im:
        assert min(im.size) < 32

    # 3. Exact duplicate (train/cat/cat_00.jpg and test/cat/cat_00_dup.jpg)
    src = (out / "train" / "cat" / "cat_00.jpg").read_bytes()
    dup = (out / "test" / "cat" / "cat_00_dup.jpg").read_bytes()
    assert src == dup

    # 4. Near duplicate: cat_01.jpg re-encoded with quality=20
    assert (out / "test" / "cat" / "cat_01_near.jpg").exists()

    # 5. Rotated copy
    rot = out / "train" / "bird" / "bird_00_rot.jpg"
    assert rot.exists()

    # 6. Leakage between train and test (covered by cat_00_dup and dog_00_near)
    assert (out / "test" / "cat" / "cat_00_dup.jpg").exists()
    assert (out / "test" / "dog" / "dog_00_near.jpg").exists()

    # 7. Mislabeled duplicate across classes
    assert (out / "test" / "dog" / "cat_02_mislabeled.jpg").exists()

    # 8. Solid-black image
    black = out / "train" / "cat" / "solid_black.png"
    assert black.exists()
    with Image.open(black) as im:
        # All pixels must be (0, 0, 0)
        im_rgb = im.convert("RGB")
        assert im_rgb.getextrema() == ((0, 0), (0, 0), (0, 0))

    # 9. Class imbalance: train/cat has many more than train/dog
    cat_count = sum(1 for _ in (out / "train" / "cat").iterdir() if _.is_file())
    dog_count = sum(1 for _ in (out / "train" / "dog").iterdir() if _.is_file())
    assert cat_count > dog_count

    # 10. Non-ASCII filename
    assert (out / "train" / "cat" / "café_ñ.jpg").exists()

    # 11. Space in filename
    assert (out / "train" / "cat" / "with space.jpg").exists()

    # 12. Wrong extension (PNG bytes with .jpg extension)
    assert (out / "train" / "dog" / "wrong_ext.jpg").exists()

    # Cleanup to keep the test directory tidy
    shutil.rmtree(out)
