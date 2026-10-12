"""Layout auto-detection and validation.

Three layouts are supported:

* ``class_folders`` — ``PATH/<class>/*.{jpg,png,...}``.
* ``split_class_folders`` — ``PATH/{train|training, val|valid|validation, test|testing}/<class>/*.{jpg,png,...}``.
* ``flat`` — files directly under ``PATH``, no labels.

The detector is intentionally simple and deterministic. It looks at the first
few entries of the root directory and at the directory depth to decide. If the
input is ambiguous (e.g. the root has both class-named subdirectories and
train/val/test subdirectories that themselves contain class subdirectories) the
detector picks ``class_folders`` and returns a warning.
"""

from __future__ import annotations

import os
from pathlib import Path

from imagedatacheck.model import Finding, Layout, Severity

SPLIT_NAMES: dict[str, str] = {
    "train": "train",
    "training": "train",
    "val": "val",
    "valid": "val",
    "validation": "val",
    "test": "test",
    "testing": "test",
}


def _is_split_name(name: str) -> bool:
    return name.lower() in SPLIT_NAMES


def _looks_like_class_folders(entries: list[Path], sample_limit: int = 32) -> bool:
    """True if at least 2 of the first non-hidden entries are directories and
    contain at least one image file each.
    """
    counts = 0
    checked = 0
    for entry in entries[:sample_limit]:
        if entry.name.startswith("."):
            continue
        if not entry.is_dir():
            continue
        checked += 1
        for child in entry.iterdir():
            if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                counts += 1
                break
    return counts >= 2


def _looks_like_split_class_folders(entries: list[Path], sample_limit: int = 32) -> bool:
    """True if at least 2 of the first non-hidden entries are split directories
    and each contains at least 2 class directories (each with an image).
    """
    split_seen = 0
    split_with_classes = 0
    for entry in entries[:sample_limit]:
        if entry.name.startswith("."):
            continue
        if not entry.is_dir():
            continue
        if not _is_split_name(entry.name):
            continue
        split_seen += 1
        class_dirs_with_image = 0
        for child in entry.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            for f in child.iterdir():
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                    class_dirs_with_image += 1
                    break
        if class_dirs_with_image >= 2:
            split_with_classes += 1
    return split_seen >= 2 and split_with_classes >= 2


#: Default set of supported image extensions. Case is normalized to lowercase.
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
)


def detect_layout(
    root: Path,
    *,
    override: Layout | None = None,
) -> tuple[Layout, list[Finding]]:
    """Detect the layout of a dataset root.

    Returns the detected layout and any findings (warnings about ambiguity).
    """
    findings: list[Finding] = []
    if not root.exists():
        return Layout.CLASS_FOLDERS, [
            Finding(
                code="E_ROOT_MISSING",
                severity=Severity.ERROR,
                message=f"Dataset root does not exist: {root}",
            )
        ]
    if not root.is_dir():
        return Layout.CLASS_FOLDERS, [
            Finding(
                code="E_ROOT_NOT_DIR",
                severity=Severity.ERROR,
                message=f"Dataset root is not a directory: {root}",
            )
        ]

    if override is not None:
        return override, []

    try:
        entries = list(root.iterdir())
    except OSError as exc:
        return Layout.CLASS_FOLDERS, [
            Finding(
                code="E_ROOT_UNREADABLE",
                severity=Severity.ERROR,
                message=f"Cannot read dataset root: {exc}",
            )
        ]

    is_split = _looks_like_split_class_folders(entries)
    is_class = _looks_like_class_folders(entries)

    if is_split and is_class:
        findings.append(
            Finding(
                code="W_LAYOUT_AMBIGUOUS",
                severity=Severity.WARNING,
                message=(
                    "Dataset matches both split_class_folders and class_folders; "
                    "falling back to class_folders. Use --layout to override."
                ),
            )
        )
        return Layout.CLASS_FOLDERS, findings

    if is_split:
        return Layout.SPLIT_CLASS_FOLDERS, findings

    if is_class:
        return Layout.CLASS_FOLDERS, findings

    # Check if it's flat (files directly under root)
    has_image = any(
        e.is_file() and e.suffix.lower() in IMAGE_EXTENSIONS
        for e in entries
        if not e.name.startswith(".")
    )
    if has_image:
        return Layout.FLAT, findings

    # Empty / no-image directory: emit an error and default to class_folders
    findings.append(
        Finding(
            code="E_EMPTY",
            severity=Severity.ERROR,
            message=f"No image files or class directories found under {root}.",
        )
    )
    return Layout.CLASS_FOLDERS, findings


def assign_label_and_split(
    root: Path,
    file_path: Path,
    layout: Layout,
) -> tuple[str | None, str | None]:
    """Return (split, label) for a file under ``root`` for the given layout.

    For ``flat``, both are ``None``. For ``class_folders``, label is the
    immediate parent directory and split is ``None``. For
    ``split_class_folders``, the split is the grandparent normalized via
    :data:`SPLIT_NAMES` and the label is the immediate parent.
    """
    rel = file_path.relative_to(root)
    parts = rel.parts
    if layout is Layout.FLAT:
        return None, None
    if layout is Layout.CLASS_FOLDERS:
        if len(parts) < 2:
            return None, None
        return None, parts[-2]
    # split_class_folders
    if len(parts) < 3:
        return None, None
    split = SPLIT_NAMES.get(parts[-3].lower())
    return split, parts[-2]


def is_hidden(path: Path) -> bool:
    """True if any component of ``path`` is hidden (starts with a dot)."""
    return any(part.startswith(".") for part in path.parts)


__all__ = [
    "Layout",
    "SPLIT_NAMES",
    "IMAGE_EXTENSIONS",
    "detect_layout",
    "assign_label_and_split",
    "is_hidden",
]


# Re-exported for the scanner module
_Severity = Severity
_Finding = Finding
del os  # not used here, kept for symmetry with the scanner
