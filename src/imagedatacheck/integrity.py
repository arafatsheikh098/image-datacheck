"""Per-file integrity checks (F3) and a multiprocessing pool (M3).

The worker is a top-level function (so it is picklable on Windows / spawn) and
returns a dict of findings for a single file. The main process collects
results and appends them to the scan result.

Multiprocessing notes
---------------------
* The default start method on Linux/macOS is ``fork``. On Windows it is
  ``spawn``; on macOS Python 3.8+ it is also ``spawn`` by default. To keep
  behaviour consistent across platforms we explicitly use ``spawn``.
* The ``if __name__ == "__main__"`` guard in the CLI is mandatory for
  ``spawn``-based multiprocessing; the worker function is a module-level
  callable so the subprocess can import this module.
* Per-file timeouts are not enforced via ``signal`` (not available in worker
  threads on Windows); instead we set Pillow's ``DECOMPRESSION_BOMB`` guard
  and rely on the full decode attempt to fail fast on malicious input. The
  ``try/except`` around the worker body makes sure one bad file never aborts
  the scan.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PIL import Image, UnidentifiedImageError

from imagedatacheck.model import Finding, Severity

# Pillow decompression bomb guard: 200 megapixels at 1 byte/pixel = 200 MB.
# Anything larger is refused to load. This is the Pillow-recommended value.
Image.MAX_IMAGE_PIXELS = 200_000_000


# Public finding codes used by the integrity module.
CODES: dict[str, str] = {
    "E_UNREADABLE": "E_UNREADABLE",
    "E_ZERO_BYTE": "E_ZERO_BYTE",
    "E_TOO_SMALL": "E_TOO_SMALL",
    "E_TRUNCATED": "E_TRUNCATED",
    "E_DECOMPRESSION_BOMB": "E_DECOMPRESSION_BOMB",
    "E_WRONG_EXTENSION": "E_WRONG_EXTENSION",
    "I_CMYK": "I_CMYK",
    "I_PALETTE_TRANSPARENCY": "I_PALETTE_TRANSPARENCY",
    "I_EXIF_ORIENTATION": "I_EXIF_ORIENTATION",
    "W_LOW_INFORMATION": "W_LOW_INFORMATION",
}


@dataclass
class IntegrityResult:
    """Return value of :func:`check_file_integrity`."""

    findings: list[Finding]
    width: int | None
    height: int | None
    mode: str | None
    is_low_info: bool
    is_cmyk: bool
    has_palette_transparency: bool
    has_exif_orientation: bool

    def to_extra(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "mode": self.mode,
            "low_info": self.is_low_info,
            "cmyk": self.is_cmyk,
            "palette_transparency": self.has_palette_transparency,
            "exif_orientation": self.has_exif_orientation,
        }


def _is_low_information(img: Image.Image) -> bool:
    """True if the image is near-constant: when converted to grayscale, the
    histogram has at most 2 non-empty bins.

    This is the standard low-information detector used to exclude solid-color
    images from near-duplicate grouping. The grayscale conversion is what
    actually matters for "is this image visually uniform".
    """
    try:
        gray = img.convert("L")
        hist = gray.histogram()
    except (OSError, ValueError):
        return False
    nonzero = sum(1 for c in hist if c > 0)
    return nonzero <= 2


def check_file_integrity(
    path: str,
    *,
    min_size: int = 32,
) -> IntegrityResult:
    """Inspect a single file and return findings plus descriptive metadata.

    Errors are non-fatal: this function always returns. ``E_UNREADABLE`` is
    used when the file cannot be opened or fully decoded.
    """
    findings: list[Finding] = []
    width: int | None = None
    height: int | None = None
    mode: str | None = None
    is_low_info = False
    is_cmyk = False
    has_palette_transparency = False
    has_exif_orientation = False

    try:
        st = os.stat(path)
    except OSError as exc:
        return IntegrityResult(
            findings=[
                Finding(
                    code=CODES["E_UNREADABLE"],
                    severity=Severity.ERROR,
                    message=f"Cannot stat {path}: {exc}",
                )
            ],
            width=None,
            height=None,
            mode=None,
            is_low_info=False,
            is_cmyk=False,
            has_palette_transparency=False,
            has_exif_orientation=False,
        )

    if st.st_size == 0:
        return IntegrityResult(
            findings=[
                Finding(
                    code=CODES["E_ZERO_BYTE"],
                    severity=Severity.ERROR,
                    message=f"Zero-byte file: {path}",
                )
            ],
            width=None,
            height=None,
            mode=None,
            is_low_info=False,
            is_cmyk=False,
            has_palette_transparency=False,
            has_exif_orientation=False,
        )

    # Open and fully decode; ``load()`` materializes pixel data which catches
    # truncated files that ``verify()`` would silently accept. We capture
    # ``DecompressionBombWarning`` (which may fire during ``Image.open()`` or
    # ``load()``) and downgrade it to a hard ``E_DECOMPRESSION_BOMB`` finding.
    import warnings

    def _bomb_finding(exc: BaseException) -> IntegrityResult:
        return IntegrityResult(
            findings=[
                Finding(
                    code=CODES["E_DECOMPRESSION_BOMB"],
                    severity=Severity.ERROR,
                    message=f"Refusing to decode (decompression bomb): {path}: {exc}",
                )
            ],
            width=None,
            height=None,
            mode=None,
            is_low_info=False,
            is_cmyk=False,
            has_palette_transparency=False,
            has_exif_orientation=False,
        )

    def _truncated_finding(exc: BaseException) -> IntegrityResult:
        return IntegrityResult(
            findings=[
                Finding(
                    code=CODES["E_TRUNCATED"],
                    severity=Severity.ERROR,
                    message=f"Cannot decode {path}: {exc}",
                )
            ],
            width=None,
            height=None,
            mode=None,
            is_low_info=False,
            is_cmyk=False,
            has_palette_transparency=False,
            has_exif_orientation=False,
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                img_ctx = Image.open(path)
            except Image.DecompressionBombWarning as exc:
                return _bomb_finding(exc)
    except (OSError, UnidentifiedImageError) as exc:
        return _truncated_finding(exc)

    try:
        with img_ctx as img:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    try:
                        img.load()
                    except Image.DecompressionBombWarning as exc:
                        return _bomb_finding(exc)
            except Image.DecompressionBombError as exc:
                return _bomb_finding(exc)
            except (OSError, UnidentifiedImageError) as exc:
                return _truncated_finding(exc)

            width, height = img.size
            mode = img.mode

            # Wrong extension (real format from Pillow's format_ attr)
            real_format = (img.format or "").lower()
            ext = os.path.splitext(path)[1].lstrip(".").lower()
            if real_format and ext and _format_extension_mismatch(real_format, ext):
                findings.append(
                    Finding(
                        code=CODES["E_WRONG_EXTENSION"],
                        severity=Severity.ERROR,
                        message=f"Extension .{ext} does not match real format {real_format} in {path}",
                    )
                )

            # CMYK mode
            if mode == "CMYK":
                is_cmyk = True
                findings.append(
                    Finding(
                        code=CODES["I_CMYK"],
                        severity=Severity.INFO,
                        message=f"CMYK image (lossy on JPEG save): {path}",
                    )
                )

            # Palette + transparency
            if mode == "P" and "transparency" in img.info:
                has_palette_transparency = True
                findings.append(
                    Finding(
                        code=CODES["I_PALETTE_TRANSPARENCY"],
                        severity=Severity.INFO,
                        message=f"Palette image with transparency: {path}",
                    )
                )

            # EXIF orientation
            exif = getattr(img, "_getexif", None)
            if exif is not None:
                try:
                    exif_data = exif()
                except Exception:
                    exif_data = None
                if exif_data and 0x0112 in exif_data:
                    has_exif_orientation = True
                    findings.append(
                        Finding(
                            code=CODES["I_EXIF_ORIENTATION"],
                            severity=Severity.INFO,
                            message=f"EXIF orientation tag present (not auto-applied): {path}",
                        )
                    )

            # Min-size check
            if min(width, height) < min_size:
                findings.append(
                    Finding(
                        code=CODES["E_TOO_SMALL"],
                        severity=Severity.ERROR,
                        message=(
                            f"Image is {width}x{height} which is below the {min_size}px threshold: {path}"
                        ),
                    )
                )

            # Low information (used later for near-duplicate exclusion)
            is_low_info = _is_low_information(img)
            if is_low_info:
                findings.append(
                    Finding(
                        code=CODES["W_LOW_INFORMATION"],
                        severity=Severity.WARNING,
                        message=f"Near-constant image (excluded from near-duplicate grouping): {path}",
                    )
                )

    except (UnidentifiedImageError, OSError) as exc:
        findings.append(
            Finding(
                code=CODES["E_UNREADABLE"],
                severity=Severity.ERROR,
                message=f"Cannot open {path}: {exc}",
            )
        )

    return IntegrityResult(
        findings=findings,
        width=width,
        height=height,
        mode=mode,
        is_low_info=is_low_info,
        is_cmyk=is_cmyk,
        has_palette_transparency=has_palette_transparency,
        has_exif_orientation=has_exif_orientation,
    )


def _format_extension_mismatch(real: str, ext: str) -> bool:
    """Return True if the file extension is wrong for the real format.

    JPEG, MPO, JPE all map to ``jpg``; PNG to ``png``; BMP to ``bmp``; GIF
    to ``gif``; TIFF to ``tif`` or ``tiff``; WEBP to ``webp``.
    """
    aliases: dict[str, set[str]] = {
        "jpeg": {"jpg", "jpeg", "jpe", "mpo"},
        "jpg": {"jpg", "jpeg", "jpe"},
        "png": {"png"},
        "bmp": {"bmp"},
        "gif": {"gif"},
        "tiff": {"tif", "tiff"},
        "tif": {"tif", "tiff"},
        "webp": {"webp"},
    }
    expected = aliases.get(real, {real})
    return ext not in expected


def run_integrity_checks(
    paths: Sequence[str],
    *,
    min_size: int = 32,
    workers: int = 1,
) -> list[Finding]:
    """Run :func:`check_file_integrity` over a list of paths.

    ``workers == 1`` uses a plain sequential loop (no multiprocessing). For
    ``workers > 1`` a process pool with the ``spawn`` start method is used.
    """
    if workers <= 1:
        out: list[Finding] = []
        for p in paths:
            out.extend(check_file_integrity(p, min_size=min_size).findings)
        return out

    # Lazy import so the CLI doesn't pay the import cost on the single-worker
    # path and so the worker function is fully importable.
    from multiprocessing import get_context

    ctx = get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        # Use a chunk size to amortize IPC overhead; 32 is a good default for
        # the small-JSON work items we send back.
        results = pool.starmap(
            _worker,
            [(p, min_size) for p in paths],
            chunksize=32,
        )
    out = []
    for r in results:
        out.extend(r)
    return out


def _worker(path: str, min_size: int) -> list[Finding]:
    """Top-level worker; must be picklable."""
    try:
        return list(check_file_integrity(path, min_size=min_size).findings)
    except Exception as exc:  # pragma: no cover - defensive
        return [
            Finding(
                code="E_UNREADABLE",
                severity=Severity.ERROR,
                message=f"Worker crashed on {path}: {exc}",
            )
        ]


__all__ = [
    "CODES",
    "IntegrityResult",
    "check_file_integrity",
    "run_integrity_checks",
    # Internal worker is exported so multiprocessing can pickle the reference
    # by qualified name in tests.
    "_worker",
]
