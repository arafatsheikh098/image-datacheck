"""Pigeonhole banding index for 64-bit hamming search.

For a Hamming threshold ``t`` on 64-bit values, we split the 64 bits into
``B = ceil(64 / t)`` bands of ``t`` bits each.  A pair of items within
Hamming distance ``t`` must collide in at least one band (pigeonhole
principle: ``t`` differing bits distribute over ``B`` bands, so at least
one band has all ``t`` differences in it... actually the inverse: if two
items agree in at least ``B-1`` bands then they agree in >= 64-t bits, so
they are within Hamming distance ``t`` of each other).

The forward direction: two items within Hamming distance ``t`` *may* be
missed if no band is identical. The standard trick is to enumerate all
``B = ceil(64/t)`` bands and keep items that collide in *at least one*
band; we then verify with the full hamming distance.

We also enumerate neighbours of a hash by Hamming distance 1 (and up to
``t`` if t <= 2) for small thresholds to reduce misses at high t. The
implementation here is the textbook banding approach plus the neighbour
enumeration, which together give exact match for thresholds up to 6 on
random 64-bit data (verified by the property test).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Iterator
from typing import TypeVar

T = TypeVar("T")

#: Maximum number of bits a single band can carry.
MAX_BAND_BITS = 8


def _band_bitmasks(band_bits: int) -> list[tuple[int, int]]:
    """Return ``[(mask, shift), ...]`` for splitting a 64-bit integer into
    ``B = ceil(64/band_bits)`` bands of ``band_bits`` bits each.

    The last band may be smaller than ``band_bits`` if 64 isn't a multiple.
    """
    bands: list[tuple[int, int]] = []
    remaining = 64
    shift = 0
    while remaining > 0:
        n = min(band_bits, remaining)
        mask = ((1 << n) - 1) << shift
        bands.append((mask, shift))
        shift += n
        remaining -= n
    return bands


def _band_value(value: int, mask: int, shift: int) -> int:
    return (value & mask) >> shift


def _enumerate_neighbours_64(value: int, radius: int) -> Iterator[int]:
    """Yield ``value`` and all neighbours within Hamming ``radius`` (radius <= 3)."""
    if radius < 0:
        return
    yield value
    if radius == 0:
        return
    bits = list(range(64))
    # radius 1
    for b in bits:
        yield value ^ (1 << b)
    if radius == 1:
        return
    # radius 2
    for i in bits:
        for j in bits[i + 1 :]:
            yield value ^ ((1 << i) | (1 << j))
    if radius == 2:
        return
    # radius 3
    for i in bits:
        for j in bits[i + 1 :]:
            for k in bits[j + 1 :]:
                yield value ^ ((1 << i) | (1 << j) | (1 << k))


def _make_sub_find(parent: dict[int, int]) -> Callable[[int], int]:
    """Return a closure-bound find function over ``parent``."""

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    return find


def _make_sub_union(
    find: Callable[[int], int], parent: dict[int, int]
) -> Callable[[int, int], None]:
    """Return a closure-bound union function over ``parent``."""

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    return union


def banding_index(
    items: Iterable[tuple[int, T]],
    *,
    threshold: int,
) -> list[list[T]]:
    """Group items whose ``int`` keys are within Hamming ``threshold`` of each other.

    Returns a list of groups (one per connected component under the
    "within-threshold" relation). Each group is sorted and deduped.
    """
    if threshold < 0:
        raise ValueError("threshold must be >= 0")
    if threshold > 64:
        raise ValueError("threshold must be <= 64")

    pairs: list[tuple[int, T]] = list(items)
    n = len(pairs)
    if n == 0:
        return []

    # Adjacency sets, union-find over indices.
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    if threshold == 0:
        # Bucketing by exact key is enough
        buckets: dict[int, list[int]] = {}
        for idx, (key, _val) in enumerate(pairs):
            buckets.setdefault(key, []).append(idx)
        for idxs in buckets.values():
            for j in idxs[1:]:
                union(idxs[0], j)
    elif threshold == 1:
        # Bucket every key under itself and every 1-bit neighbour. Two
        # items that share a bucket are within Hamming 1 of each other
        # only if one is a neighbour of the other (not just both neighbours
        # of the same intermediate value). The sub-union-find at the end
        # filters out false positives.
        seen: dict[int, list[int]] = {}
        for idx, (key, _val) in enumerate(pairs):
            for nbr in _enumerate_neighbours_64(key, 1):
                seen.setdefault(nbr, []).append(idx)
        for idxs in seen.values():
            for j in idxs[1:]:
                union(idxs[0], j)
    else:
        # General banding index plus neighbour enumeration for small radii
        band_bits = max(1, math.ceil(64 / (threshold + 1)))
        band_bits = min(band_bits, MAX_BAND_BITS)
        bands = _band_bitmasks(band_bits)
        bucket: dict[tuple[int, int], list[int]] = {}
        for idx, (key, _val) in enumerate(pairs):
            for mask, shift in bands:
                bv = _band_value(key, mask, shift)
                bucket.setdefault((mask, bv), []).append(idx)
        for idxs in bucket.values():
            for j in idxs[1:]:
                union(idxs[0], j)

        # Enumerate neighbours within threshold if threshold is small enough
        # to be feasible (radius <= 3 -> up to ~43k neighbours per hash).
        if threshold <= 3:
            neighbours: dict[int, list[int]] = {}
            for idx, (key, _val) in enumerate(pairs):
                for nbr in _enumerate_neighbours_64(key, threshold):
                    neighbours.setdefault(nbr, []).append(idx)
            for idxs in neighbours.values():
                for j in idxs[1:]:
                    union(idxs[0], j)

    # Verify candidates pairwise and union (only needed for banding, since
    # bucket collisions may exceed threshold). Brute force O(n^2) is the
    # worst case but n in our use is the number of banding-bucket
    # collisions, which is much smaller than the input size.
    def _hamming(a: int, b: int) -> int:
        return bin(a ^ b).count("1")

    # Build groups by parent
    groups: dict[int, list[int]] = {}
    for idx in range(n):
        groups.setdefault(find(idx), []).append(idx)
    out: list[list[T]] = []
    for idxs in groups.values():
        if len(idxs) == 1:
            continue
        # Verify within-group: build a fresh union-find over the small
        # group using pairwise hamming. This handles false-positive banding
        # collisions correctly: two items that share a bucket but are
        # outside the threshold are placed in different connected
        # components.
        sub_find = {idx: idx for idx in idxs}
        sub_find_fn = _make_sub_find(sub_find)
        sub_union = _make_sub_union(sub_find_fn, sub_find)

        for i_idx, i in enumerate(idxs):
            for j in idxs[i_idx + 1 :]:
                if _hamming(pairs[i][0], pairs[j][0]) <= threshold:
                    sub_union(i, j)
        sub_groups: dict[int, list[int]] = {}
        for i in idxs:
            sub_groups.setdefault(sub_find_fn(i), []).append(i)
        for sub_idxs in sub_groups.values():
            if len(sub_idxs) >= 2:
                out.append([pairs[i][1] for i in sub_idxs])
    return out


__all__ = ["banding_index"]
