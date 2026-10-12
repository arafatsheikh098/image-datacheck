"""Typed dataclasses for the scan model.

The shape defined here is what gets serialized to JSON. Adding a field is a
schema change (bump ``schema_version`` in the reporter) and must be documented
in ``docs/json_schema.md``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1


class Severity(str, enum.Enum):
    """Severity levels used by the scanner."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Layout(str, enum.Enum):
    """Supported dataset layouts."""

    CLASS_FOLDERS = "class_folders"
    SPLIT_CLASS_FOLDERS = "split_class_folders"
    FLAT = "flat"


class FailureOn(str, enum.Enum):
    """The --fail-on policy."""

    ERROR = "error"
    WARNING = "warning"
    NEVER = "never"


@dataclass
class FileInfo:
    """Information about a single image file discovered by the walker."""

    path: str  # absolute path as discovered
    rel_path: str  # path relative to dataset root
    size: int  # bytes
    split: str | None  # None for class_folders / flat
    label: str | None  # class name; None for flat

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "rel_path": self.rel_path,
            "size": self.size,
            "split": self.split,
            "label": self.label,
        }


@dataclass
class Finding:
    """A single issue, attached to one or more files (may be empty for dataset-wide)."""

    code: str
    severity: Severity
    message: str
    files: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "files": list(self.files),
            "extra": dict(self.extra),
        }


@dataclass
class ScanResult:
    """Top-level result of a scan."""

    root: str
    layout: Layout
    files: list[FileInfo]
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "root": self.root,
            "layout": self.layout.value,
            "files": [f.to_dict() for f in self.files],
            "findings": [f.to_dict() for f in self.findings],
        }
