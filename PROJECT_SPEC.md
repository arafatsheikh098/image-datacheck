PROJECT: DataCheck (final package name chosen in M1 and logged in DECISIONS.md; written as <pkg> below)
PURPOSE: A fast, trustworthy CLI that scans an image dataset folder and reports data-quality problems before training: corrupt files, duplicates, class imbalance and, most importantly, leakage between train/val/test splits and conflicting labels.

IN SCOPE
F1 CLI: `<pkg> scan PATH` (terminal summary and exit code) and `<pkg> report PATH --html out.html --json out.json` (writes files and prints the same summary). Options: --workers N (default: CPU count, 1 disables multiprocessing), --phash-threshold N (default 4), --rotation-invariant (hash 8 orientations; default off), --no-near-duplicates, --min-size N (default 32), --imbalance-ratio N (default 10), --extensions, --follow-symlinks (default off), --layout {auto,class_folders,split_class_folders,flat}, --fail-on {error,warning,never} (default error), --thumbnails N (default 50, report only), --quiet, --version.
F2 Layout detection: class_folders (PATH/class/*.jpg), split_class_folders (PATH/{train|training, val|valid|validation, test|testing}/class/*.jpg), flat (no labels; integrity and duplicate checks only). Auto-detect with an explicit override; if ambiguous, warn and use class_folders. Ignore hidden files; never follow symlink loops.
F3 Integrity checks: unreadable or corrupt files (attempt a full decode so truncated files are caught), zero-byte files, images smaller than --min-size, extension that does not match the real format, unusual modes (CMYK, palette with transparency) reported as info, EXIF orientation present reported as info, decompression-bomb guard.
F4 Duplicates: exact duplicates by SHA-256 (size prefilter); near duplicates by 64-bit perceptual hash within the Hamming threshold, found with a pigeonhole banding index (not O(n squared) comparison); optional rotation/flip invariance; low-information images (near-constant pixels) are flagged and excluded from near-duplicate grouping so that all-black images do not form giant false groups.
F5 Dataset checks: class counts; imbalance ratio; empty classes; class-name collisions after normalization (case, spaces, underscores, hyphens); cross-split leakage (exact and near duplicates present in more than one split); conflicting labels (duplicates or near-duplicates assigned to different classes), reported as likely label noise.
F6 Reports: Rich terminal summary; JSON with schema_version; a standalone single-file HTML report (no external requests, all paths and names HTML-escaped, up to --thumbnails images embedded as base64 data URIs with a size cap); deterministic ordering so reports diff cleanly. Exit codes: 0 no issues at or above --fail-on; 1 issues found at or above --fail-on; 2 usage or runtime error.
F7 Packaging and release: src layout; pyproject.toml (PEP 621); py.typed; wheel and sdist; `twine check`; CI matrix on Ubuntu, Windows and macOS with Python 3.10 and 3.12; a CI job that installs the built wheel in a clean virtualenv and runs the CLI; a tag-triggered release workflow using PyPI trusted publishing with a manual-approval environment; documented TestPyPI dry run; CHANGELOG; LICENSE (MIT); README with a GitHub Actions usage example; a workflow that publishes a sample report to GitHub Pages.
F8 Demo dataset generator: examples/make_demo_dataset.py (Pillow only, deterministic) creates a small dataset with planted problems: a corrupt file, a tiny image, an exact duplicate, a near duplicate, a rotated copy, leakage between train and test, a mislabeled duplicate across classes, a solid-black image, and class imbalance. Used by tests, docs and the sample report.

OUT OF SCOPE
GUI, video/audio/text data, automatic fixing or deleting of files, ML or embedding-based checks, cloud storage paths, plugins, config files, annotation formats (COCO, YOLO, VOC), anything not listed above.

ALLOWED STACK
Python 3.10+; Typer; Rich; Pillow; imagehash (and its numpy dependency); Jinja2 (autoescape on) for the HTML report; pytest; pytest-cov; ruff; mypy; build; twine; GitHub Actions. Nothing else without a BACKLOG entry.

GLOBAL ACCEPTANCE CRITERIA
G1 Every planted problem in the demo dataset is found, and nothing is reported on a clean control dataset (golden-file test of JSON output).
G2 The banded near-duplicate search returns exactly the same pairs as a brute-force comparison on random hash data (property-style test).
G3 Works on Windows, macOS and Linux in CI, including multiprocessing and non-ASCII file names.
G4 The wheel installs in a clean virtualenv and `<pkg> --version` and `<pkg> scan examples/demo` run.
G5 The HTML report makes no external requests and escapes hostile file names such as <script>.jpg (test).
G6 Exit codes behave exactly as specified (tests for 0, 1 and 2 with each --fail-on value).
G7 A scan of 20,000 generated small images completes with bounded memory; time and memory are measured and written to the README (numbers from your own run, with the machine described).

MILESTONES
M1 Package skeleton and CI; M2 Scanner and layout detection; M3 Integrity checks and multiprocessing; M4 Duplicate detection; M5 Dataset-level checks; M6 Reports and exit codes; M7 Packaging, release and sample report.
