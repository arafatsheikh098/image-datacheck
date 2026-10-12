"""SHA-256 exact-duplicate hashing and 64-bit perceptual hashing.

The exact-duplicate stage uses a SHA-256 over the file bytes with a size
prefilter; the perceptual-hash stage uses :mod:`imagehash` and supports
the eight orientation variants used by the ``--rotation-invariant`` flag.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

import imagehash
from PIL import Image, ImageFile

# Allow truncated files to still be loaded enough to compute a phash; the
# integrity step (M3) is responsible for reporting E_TRUNCATED. For phash
# purposes we want a best-effort decode.
ImageFile.LOAD_TRUNCATED_IMAGES = True


def sha256_of_file(path: str, *, chunk: int = 1 << 16) -> str:
    """Return the SHA-256 hex digest of the file at ``path``."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            buf = fh.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _hash_to_int(h: imagehash.ImageHash) -> int:
    """Convert an :class:`imagehash.ImageHash` to a Python int.

    ``ImageHash.hash`` is a 2D numpy bool array; we pack it as 64 bits.
    """
    import numpy as np

    flat = np.asarray(h.hash).flatten()
    out = 0
    for i, bit in enumerate(flat):
        if bit:
            out |= 1 << i
    return out


def phash64(path: str) -> int:
    """Return the 64-bit perceptual hash of an image file as a Python int.

    The integer form is convenient for banding search: low N bits can be
    masked cheaply and a tuple of (bit, position) can be a dictionary key.
    """
    with Image.open(path) as img:
        return _hash_to_int(imagehash.phash(img, hash_size=8))


#: The eight transformations of an image that count as equivalent under
#: the ``--rotation-invariant`` flag.  We precompute phashes for each.
_ROTATIONS: list[str] = [
    "original",
    "rotate90",
    "rotate180",
    "rotate270",
    "flipud",
    "flipud+rotate90",
    "flipud+rotate180",
    "flipud+rotate270",
]


#: PIL's ``Image.FLIP_TOP_BOTTOM`` constant. We import it lazily and bind
#: a local int to avoid relying on PIL type stubs that don't expose it.
_FLIP_TOP_BOTTOM = 0  # placeholder; replaced by _FLIP_TOP_BOTTOM below
try:
    from PIL import Image as _PIL_Image  # noqa: F401

    _FLIP_TOP_BOTTOM = int(getattr(_PIL_Image, "FLIP_TOP_BOTTOM", 0))
except Exception:  # pragma: no cover
    pass


def _flip(img: Image.Image) -> Image.Image:
    """Flip the image top-to-bottom. Casts the int constant to the
    Transpose enum type because PIL's stubs differ between versions."""
    from typing import cast

    from PIL.Image import Transpose

    return img.transpose(cast(Transpose, _FLIP_TOP_BOTTOM))


def _transform(img: Image.Image, name: str) -> Image.Image:
    if name == "original":
        return img
    if name == "rotate90":
        return img.rotate(90, expand=True)
    if name == "rotate180":
        return img.rotate(180, expand=True)
    if name == "rotate270":
        return img.rotate(270, expand=True)
    if name == "flipud":
        return _flip(img)
    if name == "flipud+rotate90":
        return _flip(img).rotate(90, expand=True)
    if name == "flipud+rotate180":
        return _flip(img).rotate(180, expand=True)
    if name == "flipud+rotate270":
        return _flip(img).rotate(270, expand=True)
    raise ValueError(name)


def phash64_variants(path: str) -> list[int]:
    """Return the 8 orientation-variant phashes for a file (or 1-element list
    when ``rotation_invariant`` is False)."""
    with Image.open(path) as img:
        return [
            _hash_to_int(imagehash.phash(_transform(img, name), hash_size=8)) for name in _ROTATIONS
        ]


def phash64_single(path: str) -> list[int]:
    """Return a single-element list with the image's phash. Useful as the
    default when ``--rotation-invariant`` is off."""
    return [phash64(path)]


def iter_hashes_for_paths(
    paths: Iterable[str],
    *,
    rotation_invariant: bool,
) -> Iterable[tuple[str, int]]:
    """Yield ``(path, phash_int)`` for every (path, orientation) pair.

    The same path appears multiple times when ``rotation_invariant`` is on.
    The exact-duplicate step (SHA-256) runs separately; the iterable here is
    for the banding index only.
    """
    if rotation_invariant:
        for p in paths:
            for h in phash64_variants(p):
                yield p, h
    else:
        for p in paths:
            yield p, phash64(p)


__all__ = [
    "sha256_of_file",
    "phash64",
    "phash64_variants",
    "phash64_single",
    "iter_hashes_for_paths",
]
