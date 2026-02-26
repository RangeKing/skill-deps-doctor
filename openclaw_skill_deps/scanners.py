from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class ProjectSignals:
    has_package_json: bool
    has_pyproject: bool
    has_requirements: bool
    has_dockerfile: bool


def scan_project_dir(d: Path) -> ProjectSignals:
    return ProjectSignals(
        has_package_json=(d / "package.json").exists(),
        has_pyproject=(d / "pyproject.toml").exists(),
        has_requirements=(d / "requirements.txt").exists(),
        has_dockerfile=(d / "Dockerfile").exists(),
    )


def parse_dockerfile_installs(dockerfile: Path) -> dict[str, list[str]]:
    """Best-effort extract packages from common Dockerfile install patterns."""
    txt = dockerfile.read_text(encoding="utf-8", errors="ignore")

    apt: list[str] = []
    apk: list[str] = []

    # naive patterns (good enough for hints)
    for m in re.finditer(r"apt-get\s+install\s+-y\s+([^\n;&]+)", txt):
        apt += re.split(r"\s+", m.group(1).strip())
    for m in re.finditer(r"apk\s+add\s+(?:--no-cache\s+)?([^\n;&]+)", txt):
        apk += re.split(r"\s+", m.group(1).strip())

    def clean(xs: list[str]) -> list[str]:
        out = []
        for x in xs:
            x = x.strip()
            if not x or x.startswith("-") or x in {"\\", "&&"}:
                continue
            out.append(x)
        return sorted(set(out))

    return {"apt": clean(apt), "apk": clean(apk)}
