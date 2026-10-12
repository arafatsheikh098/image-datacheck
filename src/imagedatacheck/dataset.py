"""Dataset-level checks (F5).

Operates on a list of :class:`FileInfo` plus the duplicate groups already
found. The checks are:

* class counts
* imbalance ratio (largest / smallest)
* empty classes
* class-name collisions after normalization (case, spaces, underscores, hyphens)
* cross-split leakage (exact and near duplicates present in more than one split)
* conflicting labels (duplicates assigned to different classes)

The output is a list of :class:`Finding` records. Each finding has a stable
``code`` so reports can group by code.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING

from imagedatacheck.duplicates import DuplicateGroup
from imagedatacheck.model import FileInfo, Finding, Severity

if TYPE_CHECKING:
    pass


# Public finding codes used by the dataset module.
CODES: dict[str, str] = {
    "W_IMBALANCE": "W_IMBALANCE",
    "W_EMPTY_CLASS": "W_EMPTY_CLASS",
    "W_CLASS_NAME_COLLISION": "W_CLASS_NAME_COLLISION",
    "W_CROSS_SPLIT_LEAKAGE": "W_CROSS_SPLIT_LEAKAGE",
    "W_CONFLICTING_LABELS": "W_CONFLICTING_LABELS",
}


# Codes raised by the walk/layout stage that indicate the dataset has no
# class labels (flat layout or empty dataset). The dataset checks should
# be skipped for these.
_NO_LABEL_CODES: frozenset[str] = frozenset({"E_FLAT_NO_CLASSES", "E_EMPTY"})


def _normalize_label(name: str) -> str:
    """Lower-case, strip, and replace runs of whitespace/underscore/hyphen
    with a single underscore. "Rose", "rose " and "ROSE" all collide.
    "rose" and "rosa" do not collide.
    """
    s = name.strip().lower()
    s = re.sub(r"[\s_\-]+", "_", s)
    return s


def _build_label_index(files: Iterable[FileInfo]) -> dict[str, set[str]]:
    """Group files by label. Returns ``{label: {paths}}`` for non-flat layouts.
    Labels with empty string are excluded.
    """
    by_label: dict[str, set[str]] = defaultdict(set)
    for f in files:
        if f.label:
            by_label[f.label].add(f.path)
    return dict(by_label)


def run_dataset_checks(
    files: list[FileInfo],
    duplicates: list[DuplicateGroup],
    *,
    imbalance_ratio: float = 10.0,
) -> list[Finding]:
    """Run all dataset-level checks and return a list of findings.

    The checks assume a non-flat layout. For a flat layout (no class
    labels) the cross-split leakage and conflicting-labels checks are
    skipped; imbalance and class-name collisions are not applicable
    because there are no class names to compare.
    """
    findings: list[Finding] = []

    # Build label index; bail out if we have no labels.
    by_label = _build_label_index(files)
    if not by_label:
        return findings

    # ---------- 1. Class counts and imbalance ----------
    counts = {label: len(paths) for label, paths in by_label.items()}
    if counts:
        max_count = max(counts.values())
        min_count = min(counts.values())
        if min_count > 0 and (max_count / min_count) >= imbalance_ratio:
            findings.append(
                Finding(
                    code=CODES["W_IMBALANCE"],
                    severity=Severity.WARNING,
                    message=(
                        f"Class imbalance: largest/smallest = "
                        f"{max_count}/{min_count} = {max_count / min_count:.2f} "
                        f">= {imbalance_ratio:.2f}"
                    ),
                    files=[],
                    extra={
                        "ratio": max_count / min_count,
                        "max_count": max_count,
                        "min_count": min_count,
                        "counts": dict(sorted(counts.items())),
                    },
                )
            )

    # ---------- 2. Empty classes ----------
    for label, paths in sorted(by_label.items()):
        if len(paths) == 0:
            findings.append(
                Finding(
                    code=CODES["W_EMPTY_CLASS"],
                    severity=Severity.WARNING,
                    message=f"Class '{label}' has no images.",
                    files=[],
                    extra={"label": label},
                )
            )

    # ---------- 3. Class-name collisions ----------
    norm_to_labels: dict[str, list[str]] = defaultdict(list)
    for label in by_label:
        norm_to_labels[_normalize_label(label)].append(label)
    for norm, label_list in sorted(norm_to_labels.items()):
        if len(label_list) > 1:
            findings.append(
                Finding(
                    code=CODES["W_CLASS_NAME_COLLISION"],
                    severity=Severity.WARNING,
                    message=(
                        f"Class names {label_list!r} collide after normalization "
                        f"('{norm}')."
                    ),
                    files=[],
                    extra={"normalized": norm, "labels": sorted(label_list)},
                )
            )

    # ---------- 4. Cross-split leakage + 5. Conflicting labels ----------
    if duplicates:
        # Index files by path for quick label lookup
        path_to_label: dict[str, str | None] = {f.path: f.label for f in files}
        path_to_split: dict[str, str | None] = {f.path: f.split for f in files}

        for g in duplicates:
            # Only consider groups that span at least two distinct (split, label)
            # tuples. A group where all members are in the same split+label
            # is fine; one where members differ in either split or label is
            # either leakage or a labelling problem.
            split_labels = {
                (path_to_split.get(p), path_to_label.get(p)) for p in g.members
            }
            if len(split_labels) <= 1:
                continue
            # Determine whether this is leakage (same label, different split)
            # or conflicting labels (same/some split, different label).
            distinct_labels = {lab for _sp, lab in split_labels if lab is not None}
            distinct_splits = {sp for sp, _lab in split_labels if sp is not None}
            if len(distinct_labels) > 1 and len(distinct_splits) > 1:
                # Both split and label differ: this is a duplicate with
                # multiple different labels and splits. Classify as
                # conflicting label (the higher-severity problem).
                findings.append(
                    Finding(
                        code=CODES["W_CONFLICTING_LABELS"],
                        severity=Severity.WARNING,
                        message=(
                            f"Duplicate group {g.group_id} ({g.kind}) has "
                            f"members with different labels: {sorted(distinct_labels)}."
                        ),
                        files=sorted(g.members),
                        extra={
                            "group_id": g.group_id,
                            "kind": g.kind,
                            "labels": sorted(distinct_labels),
                            "splits": sorted(distinct_splits),
                        },
                    )
                )
            elif len(distinct_splits) > 1 and len(distinct_labels) <= 1:
                # Same label, different split: leakage.
                findings.append(
                    Finding(
                        code=CODES["W_CROSS_SPLIT_LEAKAGE"],
                        severity=Severity.WARNING,
                        message=(
                            f"Duplicate group {g.group_id} ({g.kind}) leaks "
                            f"across splits: {sorted(distinct_splits)}."
                        ),
                        files=sorted(g.members),
                        extra={
                            "group_id": g.group_id,
                            "kind": g.kind,
                            "splits": sorted(distinct_splits),
                            "label": next(iter(distinct_labels), None),
                        },
                    )
                )
            elif len(distinct_labels) > 1:
                # Different label, same split (or all flat). Conflicting labels.
                findings.append(
                    Finding(
                        code=CODES["W_CONFLICTING_LABELS"],
                        severity=Severity.WARNING,
                        message=(
                            f"Duplicate group {g.group_id} ({g.kind}) has "
                            f"members with different labels: {sorted(distinct_labels)}."
                        ),
                        files=sorted(g.members),
                        extra={
                            "group_id": g.group_id,
                            "kind": g.kind,
                            "labels": sorted(distinct_labels),
                            "splits": sorted(distinct_splits),
                        },
                    )
                )

    return findings


__all__ = ["CODES", "run_dataset_checks", "_normalize_label"]
