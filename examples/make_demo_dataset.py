"""Deterministic demo dataset generator for imagedatacheck.

Run from the repository root::

    python examples/make_demo_dataset.py examples/demo

Creates a ``split_class_folders`` dataset with the following planted problems
(see F8 in PROJECT_SPEC.md):

* a corrupt file (zero-byte-sized or random bytes pretending to be JPEG)
* a tiny image (smaller than the default --min-size of 32 px on the short side)
* an exact duplicate (same bytes, two different paths)
* a near duplicate (re-saved with a different quality)
* a rotated copy (caught only with ``--rotation-invariant``)
* leakage between train and test (the same image in two splits)
* a mislabeled duplicate across classes (one copy in ``train/cat``, one in
  ``test/dog``)
* a solid-black image (low information)
* class imbalance (cat has many more samples than dog)

The generator is deterministic: two runs produce byte-identical output.
Only Pillow is required at runtime.
"""

from __future__ import annotations

import io
import os
import random
import sys
from pathlib import Path

from PIL import Image

SEED = 12345
IMG_SIZE = 96
# A distinctive per-class palette so near-duplicate detection has signal
PALETTE = {
    "cat": (220, 90, 60),
    "dog": (60, 110, 220),
    "bird": (90, 200, 90),
}
TRAIN_COUNTS = {"cat": 6, "dog": 2, "bird": 2}  # planted imbalance
TEST_COUNTS = {"cat": 1, "dog": 1, "bird": 1}


def _save_jpeg(img: Image.Image, path: Path, *, quality: int = 85) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(path, format="JPEG", quality=quality)


def _save_png_solid(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (IMG_SIZE, IMG_SIZE), color).save(path, format="PNG")


def _make_class_image(rng: random.Random, color: tuple[int, int, int], salt: int) -> Image.Image:
    """Deterministic per-(class, salt) image: a solid background with a 32x32 block of a second color."""
    base = Image.new("RGB", (IMG_SIZE, IMG_SIZE), color)
    px = base.load()
    r, g, b = color
    second = ((r + 80) % 256, (g + 80) % 256, (b + 80) % 256)
    for y in range(salt * 4 % (IMG_SIZE - 32), salt * 4 % (IMG_SIZE - 32) + 32):
        for x in range((salt * 7) % (IMG_SIZE - 32), (salt * 7) % (IMG_SIZE - 32) + 32):
            px[x, y] = second
    # Add deterministic noise seeded by salt
    for i in range(200):
        x = (salt * 13 + i * 37) % IMG_SIZE
        y = (salt * 17 + i * 41) % IMG_SIZE
        px[x, y] = ((x * 7 + y * 5) % 256, (y * 11) % 256, (x * 13) % 256)
    return base


def main(out_dir: str = "examples/demo") -> None:
    rng = random.Random(SEED)
    out = Path(out_dir).resolve()
    if out.exists():
        # Deterministic regeneration: clear and re-create
        import shutil

        shutil.rmtree(out)
    out.mkdir(parents=True)

    # ------- TRAIN -------
    for cls, count in TRAIN_COUNTS.items():
        cls_dir = out / "train" / cls
        cls_dir.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            img = _make_class_image(rng, PALETTE[cls], i)
            _save_jpeg(img, cls_dir / f"{cls}_{i:02d}.jpg")

    # ------- TEST -------
    for cls, count in TEST_COUNTS.items():
        cls_dir = out / "test" / cls
        cls_dir.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            img = _make_class_image(rng, PALETTE[cls], i + 100)
            _save_jpeg(img, cls_dir / f"{cls}_{i:02d}.jpg")

    # ------- Planted problems -------

    # 1. Exact duplicate: cat_00 in train re-saved to test/cat/cat_00_dup.jpg
    src = out / "train" / "cat" / "cat_00.jpg"
    dup = out / "test" / "cat" / "cat_00_dup.jpg"
    dup.parent.mkdir(parents=True, exist_ok=True)
    dup.write_bytes(src.read_bytes())

    # 2. Near duplicate: cat_01 re-encoded with a different JPEG quality
    src = out / "train" / "cat" / "cat_01.jpg"
    near = out / "test" / "cat" / "cat_01_near.jpg"
    img = Image.open(src)
    _save_jpeg(img, near, quality=20)

    # 3. Leakage between train and test (covered by exact duplicate above;
    #    add a near duplicate that crosses splits too)
    src = out / "train" / "dog" / "dog_00.jpg"
    near = out / "test" / "dog" / "dog_00_near.jpg"
    img = Image.open(src)
    _save_jpeg(img, near, quality=30)

    # 4. Rotated copy: same image rotated 90 degrees (only caught with --rotation-invariant)
    src = out / "train" / "bird" / "bird_00.jpg"
    rot = out / "train" / "bird" / "bird_00_rot.jpg"
    img = Image.open(src).rotate(90)
    _save_jpeg(img, rot)

    # 5. Mislabeled duplicate: cat_02 in train, same image in test/dog/
    src = out / "train" / "cat" / "cat_02.jpg"
    bad = out / "test" / "dog" / "cat_02_mislabeled.jpg"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(src.read_bytes())

    # 6. Solid-black image (low information)
    _save_png_solid(out / "train" / "cat" / "solid_black.png", (0, 0, 0))

    # 7. Tiny image (16x16) in train/bird
    tiny = Image.new("RGB", (16, 16), PALETTE["bird"])
    _save_jpeg(tiny, out / "train" / "bird" / "tiny.jpg")

    # 8. Corrupt file: deterministic random bytes with a .jpg extension
    corrupt_bytes = bytes(rng.getrandbits(8) for _ in range(256)) + b"\xff\xd8\xff\xe0"
    (out / "train" / "cat" / "corrupt.jpg").write_bytes(corrupt_bytes)

    # 9. Wrong extension: a PNG saved as .jpg
    png_bytes = io.BytesIO()
    Image.new("RGB", (IMG_SIZE, IMG_SIZE), (200, 100, 50)).save(png_bytes, format="PNG")
    (out / "train" / "dog" / "wrong_ext.jpg").write_bytes(png_bytes.getvalue())

    # 10. Non-ASCII filename (proves non-ASCII paths work)
    non_ascii = out / "train" / "cat" / "café_ñ.jpg"
    img = _make_class_image(rng, PALETTE["cat"], 999)
    _save_jpeg(img, non_ascii)

    # 11. Space in filename
    spaced = out / "train" / "cat" / "with space.jpg"
    img = _make_class_image(rng, PALETTE["cat"], 888)
    _save_jpeg(img, spaced)

    # Summary
    file_count = sum(1 for _ in out.rglob("*") if _.is_file())
    print(f"Demo dataset written to {out} ({file_count} files)")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "examples/demo"
    main(target)
