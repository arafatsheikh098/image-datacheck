"""Thin Rich-progress wrapper that respects --quiet and non-tty stdout."""

from __future__ import annotations

import sys
from collections.abc import Iterable

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)


def make_progress(quiet: bool) -> Progress | None:
    """Return a :class:`rich.progress.Progress` or ``None`` if disabled."""
    if quiet or not sys.stdout.isatty():
        return None
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        transient=True,
    )


def iter_with_progress(
    items: Iterable[object],
    total: int,
    description: str,
    progress: Progress | None,
) -> Iterable[object]:
    """Yield items, optionally showing a progress bar. Identity if ``progress`` is None."""
    if progress is None:
        yield from items
        return
    task_id = progress.add_task(description, total=total)
    with progress:
        for item in items:
            yield item
            progress.advance(task_id)


__all__ = ["make_progress", "iter_with_progress"]
