# PLAN.md

> Per-milestone delivery plan. Each milestone ends with a Milestone Gate (CLAUDE.md).

## M1 — Package skeleton and CI
**Files to create**
- `pyproject.toml` (PEP 621, src layout, Typer CLI entry point, dependencies pinned)
- `src/<pkg>/__init__.py` (package marker, single source of truth for `__version__`)
- `src/<pkg>/__main__.py` (calls Typer app; `python -m <pkg>`)
- `src/<pkg>/cli.py` (Typer app with `--version` and a `scan` stub so the import works)
- `tests/test_cli.py` (test that `--version` prints version; test `scan` is wired)
- `tests/test_version.py` (single source of truth check)
- `ruff.toml` or `[tool.ruff]` in `pyproject.toml`
- `[tool.mypy]` config in `pyproject.toml`; `mypy.ini` if needed
- `[tool.pytest.ini_options]` in `pyproject.toml`
- `README.md` (stub: install + run)
- `.github/workflows/ci.yml` (matrix: ubuntu/windows/macos, Python 3.10/3.12; lint, type, test)
- `.gitignore`
- `DECISIONS.md` (entry: chosen PyPI name + verification)

**Tests**
- `test_version.py::test_version_is_string` — `__version__` is a non-empty string.
- `test_cli.py::test_version_flag` — `python -m <pkg> --version` prints version and exits 0.
- `test_cli.py::test_help_flag` — `--help` exits 0.

**Acceptance**
- A1 `pip install -e .[dev]` works locally and on all CI platforms.
- A2 `<pkg> --version` prints the version from a single source of truth.
- A3 CI is green on all matrix entries.
- A4 The chosen name and verification output are recorded in `DECISIONS.md`.

## M2 — Scanner and layout detection
**Files to create / change**
- `src/<pkg>/scanner.py` (directory walker: hidden files, symlink loop guard, supported extensions, deterministic order)
- `src/<pkg>/layout.py` (layout auto-detection: `class_folders`, `split_class_folders`, `flat`, ambiguity handling, `--layout` override)
- `src/<pkg>/model.py` (typed dataclasses: `ScanResult`, `FileInfo`, `Layout`, plus JSON serialization helpers)
- `src/<pkg>/progress.py` (Rich progress bar; disabled when `--quiet` or non-tty)
- `src/<pkg>/cli.py` (wire `scan` to scanner; add `--quiet`, `--extensions`, `--follow-symlinks`, `--layout`)
- `examples/make_demo_dataset.py` (F8 generator with all planted problems; Pillow only; deterministic)
- `tests/test_scanner.py` (hidden files, deterministic order, empty folder, missing path → exit 2)
- `tests/test_layout.py` (each layout on fixtures, ambiguous fallback, `--layout` override)
- `tests/test_demo.py` (demo generator is deterministic and contains every planted problem file)

**Acceptance**
- A1 Each of the three layouts is detected correctly on generated fixtures.
- A2 Ambiguous layout warns and falls back to `class_folders`.
- A3 Symlink loop does not hang (test, skipped where symlinks unavailable).
- A4 Non-ASCII and space-containing paths work on all platforms.
- A5 Results are in deterministic order.
- A6 Empty folder and missing path return a clear error with exit code 2.

## M3 — Integrity checks and multiprocessing
**Files to create / change**
- `src/<pkg>/integrity.py` (worker function: decode attempt, zero-byte, min-size, format vs extension, CMYK / palette+transparency / EXIF orientation info, decompression-bomb guard, low-info detector)
- `src/<pkg>/pool.py` (chunked parallel processing; `multiprocessing.Pool` with `spawn` start method; safe single-process fallback when `--workers 1`; per-file error capture)
- `src/<pkg>/scanner.py` (call pool with chunked files)
- `src/<pkg>/cli.py` (add `--workers`, `--min-size`)
- `tests/test_integrity.py` (per-fixture per-finding; identical results with --workers 1 and 4; one bad file does not abort)
- `tests/test_pool.py` (spawn method used; main guard present; works on all OSes)
- `tests/test_memory.py` (memory bounded on 20k small images; measured; CI may skip on size)

**Acceptance**
- A1 Truncated, zero-byte, tiny, wrong-extension, and decompression-bomb files each reported.
- A2 Results identical with `--workers 1` and `--workers 4` (test).
- A3 Multiprocessing works on Windows and macOS in CI.
- A4 One unreadable file never aborts the scan.
- A5 Memory bounded on 20k images (measured).

## M4 — Duplicate detection
**Files to create / change**
- `src/<pkg>/hashes.py` (SHA-256 with size prefilter, 64-bit perceptual hash, 8-orientation variant)
- `src/<pkg>/banding.py` (pigeonhole banding index for 64-bit hamming search)
- `src/<pkg>/duplicates.py` (group builder; excludes low-info images; assigns stable group ids)
- `src/<pkg>/scanner.py` (post integrity, run duplicate detection)
- `src/<pkg>/cli.py` (add `--phash-threshold`, `--rotation-invariant`, `--no-near-duplicates`)
- `tests/test_banding.py` (property test: random 64-bit hashes vs brute force, thresholds 0..6)
- `tests/test_duplicates.py` (exact, re-saved, resized, rotated+flipped, unrelated not grouped, solid colors excluded, transitive grouping, stable group ids)

**Acceptance**
- A1 Banded search equals brute force on random hashes for thresholds 0..6.
- A2 Exact, re-saved, resized, and (with `--rotation-invariant`) rotated/flipped are found; unrelated is not.
- A3 Solid-black and solid-white images do not form groups.
- A4 Grouping is transitive and deterministic.
- A5 20k images finish within README time.

## M5 — Dataset-level checks
**Files to create / change**
- `src/<pkg>/dataset.py` (class counts, imbalance ratio, empty classes, class-name collisions, cross-split leakage, conflicting labels)
- `src/<pkg>/scanner.py` (post duplicates, run dataset checks)
- `src/<pkg>/cli.py` (add `--imbalance-ratio`)
- `tests/test_dataset.py` (leakage golden test, conflicting label, collisions, imbalance boundary, clean control)
- `tests/fixtures/clean_control/` (small clean dataset for golden test)

**Acceptance**
- A1 Leakage between train and test reported with both file paths (golden).
- A2 Duplicate in two classes reported as conflicting label.
- A3 "Rose", "rose " and "ROSE" collide; "rose" and "rosa" do not.
- A4 Imbalance threshold respected at exact boundary.
- A5 Clean control dataset produces zero findings.

## M6 — Reports and exit codes
**Files to create / change**
- `src/<pkg>/reporters/rich_summary.py` (terminal summary)
- `src/<pkg>/reporters/json_report.py` (JSON with `schema_version`; deterministic; documented schema in `docs/json_schema.md`)
- `src/<pkg>/reporters/html_report.py` (Jinja2 with autoescape, embedded base64 thumbnails, no external requests)
- `src/<pkg>/reporters/templates/report.html.j2`
- `src/<pkg>/report.py` (orchestrator: `report` subcommand writes files and prints summary)
- `src/<pkg>/exitcodes.py` (compute exit code from findings + `--fail-on`)
- `src/<pkg>/cli.py` (add `report` subcommand, `--fail-on`, `--thumbnails`, `--html`, `--json`)
- `docs/json_schema.md`
- `tests/test_reports.py` (JSON golden, HTML escape, no external refs, `--thumbnails 0`, byte-identical, exit codes per --fail-on)

**Acceptance**
- A1 JSON matches golden for demo dataset.
- A2 Hostile filename escaped; HTML has no http(s) external references.
- A3 Exit codes 0, 1, 2 verified for each --fail-on.
- A4 `--thumbnails 0` produces no embedded images; size cap holds.
- A5 Two runs give byte-identical JSON (timestamp excluded by default).

## M7 — Packaging, release and sample report
**Files to create / change**
- `pyproject.toml` (build backend, package data includes template)
- `CHANGELOG.md`
- `LICENSE` (MIT)
- `RELEASING.md` (TestPyPI dry run, PyPI trusted publisher fields, environment reviewer, tag flow)
- `README.md` (final; usage example with GitHub Actions)
- `.github/workflows/release.yml` (tag-triggered; trusted publishing; environment `pypi` with required reviewer; never on PRs)
- `.github/workflows/pages.yml` (build demo dataset, generate sample report, publish to GitHub Pages)
- `scripts/smoke_test.sh`
- `scripts/measure_perf.py` (runs 20k scan, records time and memory; writes `perf.json`)
- `tests/test_release_workflow.py` (lints YAML; asserts no `pull_request:` trigger)
- Performance numbers copied from `perf.json` into `README.md`.

**Acceptance**
- A1 CI builds wheel, installs in clean venv, runs `<pkg> scan` on demo.
- A2 `twine check` passes.
- A3 Release workflow is syntactically valid; never runs on PRs.
- A4 RELEASING.md lists every manual step in order.
- A5 README performance numbers come from a recorded run.
