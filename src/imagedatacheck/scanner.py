"""Directory walker that collects :class:`FileInfo` records.

The walker:

* skips hidden files and directories (any component starting with ``.``),
* refuses to follow symlink loops by tracking visited inodes,
* supports the ``--follow-symlinks`` flag (off by default),
* returns a deterministically ordered list (sorted by relative path).
"""

from __future__ import annotations

import os
from pathlib import Path

from imagedatacheck.layout import (
    IMAGE_EXTENSIONS,
    Layout,
    assign_label_and_split,
    is_hidden,
)
from imagedatacheck.model import FileInfo, Finding, ScanResult, Severity

_MAX_INODE_BUDGET = 1_000_000  # safety: never track more than this many inodes


class WalkerState:
    """Mutable state carried through a recursive walk to detect loops and bound work."""

    __slots__ = ("visited_inodes", "follow_symlinks")

    def __init__(self, follow_symlinks: bool) -> None:
        self.visited_inodes: set[tuple[int, int]] = set()
        self.follow_symlinks = follow_symlinks

    def add(self, path: Path) -> bool:
        """Register ``path``; return False if we have already visited it (loop)."""
        try:
            st = path.stat()
        except OSError:
            return True
        key = (st.st_dev, st.st_ino)
        if key in self.visited_inodes:
            return False
        if len(self.visited_inodes) >= _MAX_INODE_BUDGET:
            # Don't refuse new files, but stop growing the set
            return True
        self.visited_inodes.add(key)
        return True


def walk(
    root: Path,
    *,
    layout: Layout,
    extensions: set[str] | None = None,
    follow_symlinks: bool = False,
) -> tuple[list[FileInfo], list[Finding]]:
    """Walk ``root`` and return (files, findings).

    ``extensions`` is a set of lowercase leading-dot extensions; defaults to
    :data:`imagedatacheck.layout.IMAGE_EXTENSIONS`. Hidden files are skipped.
    Symlink loops are detected via inode tracking.
    """
    exts = extensions or IMAGE_EXTENSIONS
    findings: list[Finding] = []
    files: list[FileInfo] = []
    state = WalkerState(follow_symlinks=follow_symlinks)

    # Special case: flat layout — files at the top level
    if layout is Layout.FLAT:
        for child in sorted(root.iterdir(), key=lambda p: str(p)):
            if is_hidden(child):
                continue
            if child.is_file() and child.suffix.lower() in exts:
                _try_add_file(state, root, child, layout, files)
        return files, findings

    def recurse(directory: Path) -> None:
        try:
            entries = list(directory.iterdir())
        except OSError as exc:
            findings.append(
                Finding(
                    code="E_DIR_UNREADABLE",
                    severity=Severity.ERROR,
                    message=f"Cannot read directory {directory}: {exc}",
                )
            )
            return
        entries.sort(key=lambda p: str(p))
        for entry in entries:
            if is_hidden(entry):
                continue
            try:
                is_link = entry.is_symlink()
            except OSError:
                continue
            if is_link and not state.follow_symlinks:
                continue
            try:
                if entry.is_dir():
                    if not state.add(entry):
                        findings.append(
                            Finding(
                                code="W_SYMLINK_LOOP",
                                severity=Severity.WARNING,
                                message=f"Symlink loop detected at {entry}, skipping subtree.",
                            )
                        )
                        continue
                    recurse(entry)
                elif entry.is_file() and entry.suffix.lower() in exts:
                    _try_add_file(state, root, entry, layout, files)
            except OSError:
                # Filesystem race; skip silently
                continue

    recurse(root)
    return files, findings


def _try_add_file(
    state: WalkerState,
    root: Path,
    path: Path,
    layout: Layout,
    out: list[FileInfo],
) -> None:
    try:
        st = path.stat()
    except OSError:
        return
    # On a symlinked file, treat it as a new file only if follow_symlinks is on
    if path.is_symlink() and not state.follow_symlinks:
        return
    rel = str(path.relative_to(root))
    split, label = assign_label_and_split(root, path, layout)
    out.append(
        FileInfo(
            path=str(path),
            rel_path=rel,
            size=int(st.st_size),
            split=split,
            label=label,
        )
    )


def make_scan_result(
    root: Path,
    layout: Layout,
    files: list[FileInfo],
    findings: list[Finding],
) -> ScanResult:
    """Build a :class:`ScanResult` and append the standard empty-folder finding if applicable."""
    if layout is not Layout.FLAT and not files:
        findings.append(
            Finding(
                code="E_EMPTY",
                severity=Severity.ERROR,
                message=f"No image files found under {root}.",
            )
        )
    # Deterministic order: by rel_path
    files.sort(key=lambda f: f.rel_path)
    findings.sort(key=lambda f: (f.severity.value, f.code, f.message))
    return ScanResult(root=str(root), layout=layout, files=files, findings=findings)


__all__ = ["walk", "make_scan_result"]


# Eagerly silence the linter about unused ``os`` (kept for portability
# of the ``os.path.sep`` constant if we ever need it).
_ = os.sep
