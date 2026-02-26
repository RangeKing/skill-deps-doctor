from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


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
