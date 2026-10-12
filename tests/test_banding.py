"""Property tests for the pigeonhole banding index.

We verify that ``banding_index`` on random 64-bit keys returns exactly the
same groups as a brute-force O(n^2) pairwise Hamming check, for every
threshold in 0..6.
"""

from __future__ import annotations

import random

from imagedatacheck.banding import banding_index


def _brute_force_groups(pairs: list[tuple[int, str]], threshold: int) -> list[list[str]]:
    """O(n^2) verification: connected components under the 'within
    threshold' relation."""
    n = len(pairs)
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

    for i in range(n):
        for j in range(i + 1, n):
            if bin(pairs[i][0] ^ pairs[j][0]).count("1") <= threshold:
                union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out: list[list[str]] = []
    for idxs in groups.values():
        if len(idxs) >= 2:
            out.append(sorted(pairs[i][1] for i in idxs))
    return sorted(out)


def _normalize(groups: list[list[str]]) -> list[tuple[str, ...]]:
    return sorted(tuple(sorted(g)) for g in groups)


def test_banding_matches_brute_force_random() -> None:
    """Random 64-bit keys: banding equals brute force for t in 0..6."""
    rng = random.Random(0xC0FFEE)
    for n, threshold in [(20, 0), (40, 1), (60, 2), (80, 3), (100, 4), (50, 5), (40, 6)]:
        pairs = [(rng.getrandbits(64), f"k{i}") for i in range(n)]
        actual = _normalize(banding_index(pairs, threshold=threshold))
        expected = _normalize(_brute_force_groups(pairs, threshold))
        assert actual == expected, (
            f"mismatch at n={n}, threshold={threshold}: actual={actual}, expected={expected}"
        )


def test_banding_empty() -> None:
    assert banding_index([], threshold=4) == []


def test_banding_single_item() -> None:
    assert banding_index([(123, "x")], threshold=4) == []


def test_banding_invalid_threshold() -> None:
    import pytest

    with pytest.raises(ValueError):
        banding_index([(1, "a")], threshold=-1)
    with pytest.raises(ValueError):
        banding_index([(1, "a")], threshold=65)


def test_banding_threshold_0_exact_only() -> None:
    pairs = [(1, "a"), (1, "b"), (2, "c"), (2, "d"), (3, "e")]
    groups = _normalize(banding_index(pairs, threshold=0))
    assert groups == [("a", "b"), ("c", "d")]


def test_banding_threshold_1_catches_one_bit_flip() -> None:
    # Two pairs differ by 1 bit each; threshold 1 must catch both.
    # Note: 0 and 0b100 are 2 bits apart, so all four keys form a
    # single connected component under threshold 1 (via 0-1 and 4-5).
    pairs = [(0b0, "a"), (0b1, "b"), (0b100, "c"), (0b101, "d")]
    groups = _normalize(banding_index(pairs, threshold=1))
    # All four should end up in one group
    assert groups == [("a", "b", "c", "d")]


def test_banding_threshold_1_rejects_2_bits_apart() -> None:
    # Two pairs of keys 2 bits apart; threshold 1 must NOT group them.
    pairs = [(0b0, "a"), (0b11, "b"), (0b1100, "c"), (0b1111, "d")]
    groups = _normalize(banding_index(pairs, threshold=1))
    assert groups == []
