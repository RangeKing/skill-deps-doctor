from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    kind: str
    item: str
    detail: str
    fix: str | None = None
    severity: str = "error"  # "error" | "warn" | "info"


@dataclass
class CheckContext:
    """Execution context passed to built-in checkers and plugins."""

    skills_dir: Path
    check_dir: Path | None = None
    probe: bool = False
    profiles: list[str] = field(default_factory=list)
    recursive: bool = False
