"""Measure 20k scan time and memory; not part of the regular test suite.

Run from the repo root with the development virtualenv:

    .venv/bin/python scripts/measure_20k.py

Measures the full M3 + M4 pipeline (layout detection, walk, integrity,
exact + near-duplicate detection).
"""

from __future__ import annotations

import os
import resource
import shutil
import sys
import time
from pathlib import Path

# Make the in-tree package importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image  # noqa: E402

from imagedatacheck.duplicates import (  # noqa: E402
    find_exact_duplicates,
    find_near_duplicates,
)
from imagedatacheck.integrity import run_integrity  # noqa: E402
from imagedatacheck.layout import detect_layout  # noqa: E402
from imagedatacheck.scanner import walk  # noqa: E402


def main(n: int = 20_000) -> None:
    root = Path(".big_perf")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    classes = ["a", "b", "c"]
    per, rem = divmod(n, len(classes))
    counts = [per + (1 if i < rem else 0) for i in range(len(classes))]

    for cls, k in zip(classes, counts, strict=False):
        cls_dir = root / "train" / cls
        cls_dir.mkdir(parents=True, exist_ok=True)
        for i in range(k):
            Image.new("RGB", (32, 32), (i % 256, 50, 100)).save(
                cls_dir / f"{cls}_{i:05d}.jpg",
                format="JPEG",
                quality=70,
            )

    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t0 = time.perf_counter()
    layout, _ = detect_layout(root)
    files, _ = walk(root, layout=layout)
    file_paths = [f.path for f in files]
    report = run_integrity(file_paths, min_size=32, workers=4)
    find_exact_duplicates(file_paths)
    find_near_duplicates(
        file_paths,
        threshold=4,
        rotation_invariant=False,
        low_info_paths=report.low_info,
    )
    dt = time.perf_counter() - t0
    rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform.startswith("linux"):
        delta_mb = (rss1 - rss0) / 1024
    else:
        delta_mb = (rss1 - rss0) / (1024 * 1024)
    print(f"files={len(files)} elapsed={dt:.2f}s peak_rss_delta={delta_mb:.0f}MB")
    shutil.rmtree(root)


if __name__ == "__main__":
    main(int(os.environ.get("IDC_PERF_N", 20_000)))
