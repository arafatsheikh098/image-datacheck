"""Exit code computation for the CLI (M6).

Three exit codes are defined:

* ``0`` — no findings at or above the ``--fail-on`` threshold.
* ``1`` — at least one finding at or above the threshold was emitted.
* ``2`` — usage or runtime error (caller raises :class:`typer.Exit` directly).

The runtime-error cases (E_EMPTY, E_ROOT_MISSING, E_ROOT_NOT_DIR) always
return 2 regardless of ``--fail-on`` because they mean the scan could not
run, not that the data was bad.
"""

from __future__ import annotations

from collections.abc import Iterable

from imagedatacheck.model import FailureOn, Finding, Severity

_RUNTIME_ERROR_CODES: frozenset[str] = frozenset(
    {"E_EMPTY", "E_ROOT_MISSING", "E_ROOT_NOT_DIR", "E_DIR_UNREADABLE"}
)


def compute_exit_code(findings: Iterable[Finding], fail_on: FailureOn) -> int:
    """Return 0/1/2 per the rules above."""
    fs = list(findings)
    if any(f.code in _RUNTIME_ERROR_CODES for f in fs):
        return 2
    if fail_on is FailureOn.NEVER:
        return 0
    if fail_on is FailureOn.ERROR:
        threshold = Severity.ERROR
    else:  # WARNING
        threshold = Severity.WARNING
    order = {Severity.ERROR: 2, Severity.WARNING: 1, Severity.INFO: 0}
    cutoff = order[threshold]
    for f in fs:
        if order[f.severity] >= cutoff:
            return 1
    return 0


__all__ = ["compute_exit_code"]
