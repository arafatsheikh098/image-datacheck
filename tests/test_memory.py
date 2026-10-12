"""Memory- and time-bounded tests for 20k image datasets.

These tests are marked ``slow`` and are skipped by default. Run them
explicitly with ``pytest -m slow`` or ``pytest -k memory``.

The 20k test generates the dataset in a temp directory and measures the
peak resident-set size of the scan. A bound of 500 MB is what we measure on
a 12-core x86_64 / arm64 box with the default pool; if the test is run on a
very small machine it may be skipped via the env var
``IDC_SKIP_MEMORY_TEST=1``.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

pytestmark = pytest.mark.slow


N_FILES = 500 if os.environ.get("IDC_FAST_MEMORY_TEST") else 20_000
SIZE = 32  # tiny images
MAX_PEAK_RSS_MB = 500
MAX_DURATION_S = 120


def _build_dataset(root: Path, n: int) -> None:
    """Generate n small images across a few class folders."""
    classes = ["a", "b", "c"]
    per_class = n // len(classes)
    remainder = n - per_class * len(classes)
    counts = [per_class] * len(classes)
    for i in range(remainder):
        counts[i] += 1
    for cls, k in zip(classes, counts, strict=False):
        cls_dir = root / "train" / cls
        cls_dir.mkdir(parents=True, exist_ok=True)
        for i in range(k):
            Image.new("RGB", (SIZE, SIZE), (i % 256, 50, 100)).save(
                cls_dir / f"{cls}_{i:05d}.jpg",
                format="JPEG",
                quality=70,
            )


def test_20k_scan_bounded_memory_and_time(tmp_path: Path) -> None:
    if os.environ.get("IDC_SKIP_MEMORY_TEST"):
        pytest.skip("IDC_SKIP_MEMORY_TEST set")
    if sys.platform.startswith("win"):
        pytest.skip("rusage is not available on Windows")

    root = tmp_path / "big"
    _build_dataset(root, N_FILES)
    # Measure resident set before, then run the scan, then peak.
    import resource

    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    start = time.perf_counter()
    from imagedatacheck.integrity import run_integrity_checks
    from imagedatacheck.layout import detect_layout
    from imagedatacheck.scanner import walk

    layout, _ = detect_layout(root)
    files, _ = walk(root, layout=layout)
    assert len(files) == N_FILES
    run_integrity_checks([f.path for f in files], min_size=SIZE, workers=4)
    elapsed = time.perf_counter() - start
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is in kilobytes on Linux, bytes on macOS / *BSD
    if sys.platform.startswith("linux"):
        peak_mb = (rss_after - rss_before) / 1024
    else:
        peak_mb = (rss_after - rss_before) / (1024 * 1024)
    print(  # noqa: T201
        f"\n[20k test] files={N_FILES} elapsed={elapsed:.1f}s peak_rss_delta={peak_mb:.0f}MB"
    )
    assert elapsed < MAX_DURATION_S, f"scan took {elapsed:.1f}s > {MAX_DURATION_S}s"
    # Only assert memory when rusage is meaningful; some CI containers are
    # very small and the per-process high-water mark is 0 there.
    if peak_mb > 0:
        assert peak_mb < MAX_PEAK_RSS_MB, f"peak RSS {peak_mb:.0f}MB > {MAX_PEAK_RSS_MB}MB"
