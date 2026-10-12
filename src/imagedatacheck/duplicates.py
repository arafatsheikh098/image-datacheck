"""Exact and near-duplicate detection (F4).

Pipeline
--------
1. SHA-256 with a size prefilter: group files with identical bytes.
2. Perceptual hash (64-bit) for every file (or 8 variants under
   ``--rotation-invariant``). Low-information images are skipped.
3. Banding index on the per-file (or per-orientation) hashes with the
   requested threshold. Group ids are stable across runs (deterministic).

The output is a list of :class:`DuplicateGroup` records. Each record has
a stable ``group_id`` (string of the SHA-256 of the sorted member paths)
so reports diff cleanly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from imagedatacheck.hashes import (
    phash64,
    phash64_variants,
    sha256_of_file,
)


@dataclass
class DuplicateGroup:
    """A group of files that are exact or near duplicates of each other."""

    group_id: str
    kind: str  # "exact" or "near"
    members: list[str]  # paths


def _stable_group_id(paths: Sequence[str]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def find_exact_duplicates(paths: Iterable[str]) -> list[DuplicateGroup]:
    """Group paths by exact SHA-256 (with a size prefilter)."""
    by_size: dict[int, list[str]] = {}
    sizes: dict[str, int] = {}
    for p in paths:
        try:
            # Cheap size prefilter using os.path.getsize
            import os

            sz = os.path.getsize(p)
        except OSError:
            continue
        sizes[p] = sz
        by_size.setdefault(sz, []).append(p)
    out: list[DuplicateGroup] = []
    for _sz, group in by_size.items():
        if len(group) < 2:
            continue
        buckets: dict[str, list[str]] = {}
        for p in group:
            try:
                digest = sha256_of_file(p)
            except OSError:
                continue
            buckets.setdefault(digest, []).append(p)
        for _digest, members in buckets.items():
            if len(members) >= 2:
                out.append(
                    DuplicateGroup(
                        group_id=_stable_group_id(members),
                        kind="exact",
                        members=sorted(members),
                    )
                )
    out.sort(key=lambda g: g.group_id)
    return out


def find_near_duplicates(
    paths: Iterable[str],
    *,
    threshold: int,
    rotation_invariant: bool,
    low_info_paths: set[str] | None = None,
) -> list[DuplicateGroup]:
    """Group paths whose 64-bit phash is within Hamming ``threshold``.

    Files in ``low_info_paths`` (e.g. solid-colour images) are excluded from
    grouping entirely.
    """
    from imagedatacheck.banding import banding_index

    low_info = low_info_paths or set()
    items: list[tuple[int, str]] = []
    for p in paths:
        if p in low_info:
            continue
        try:
            if rotation_invariant:
                for h in phash64_variants(p):
                    items.append((h, p))
            else:
                items.append((phash64(p), p))
        except Exception:
            continue
    groups = banding_index(items, threshold=threshold)
    out: list[DuplicateGroup] = []
    seen_groups: set[tuple[str, ...]] = set()
    for member_list in groups:
        # Deduplicate paths inside the group (orientation variants can
        # produce the same path multiple times).
        unique_members = sorted(set(member_list))
        if len(unique_members) < 2:
            continue
        key = tuple(unique_members)
        if key in seen_groups:
            continue
        seen_groups.add(key)
        out.append(
            DuplicateGroup(
                group_id=_stable_group_id(unique_members),
                kind="near",
                members=unique_members,
            )
        )
    out.sort(key=lambda g: g.group_id)
    return out


__all__ = [
    "DuplicateGroup",
    "find_exact_duplicates",
    "find_near_duplicates",
]
