# Changelog

All notable changes to imagedatacheck are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

* M4: exact and near-duplicate detection with banding index.
* M5: dataset-level checks (imbalance, empty classes, class-name
  collisions, cross-split leakage, conflicting labels).
* M6: Rich terminal summary, JSON reporter (schema_version=1) and
  standalone HTML reporter with embedded base64 thumbnails.
* M6: ``report`` subcommand with ``--html``, ``--json``, ``--thumbnails``,
  ``--fail-on`` flags.
* M6: central ``compute_exit_code`` helper covering exit codes 0, 1, 2.

## [0.1.0] - 2026-10-12

### Added

* Initial release.
* M1: package skeleton, Typer CLI, GitHub Actions matrix CI (Ubuntu,
  Windows, macOS, Python 3.10/3.12).
* M2: directory walker with symlink-loop guard, layout auto-detection
  (class_folders / split_class_folders / flat), deterministic results,
  non-ASCII and space-containing paths supported.
* M3: per-file integrity checks (corrupt, zero-byte, too small, wrong
  extension, CMYK, palette-with-transparency, EXIF orientation,
  decompression-bomb guard, low-information), multiprocessing with
  the ``spawn`` start method, 20k-image benchmark under 2.5s.
