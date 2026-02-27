from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectSignals:
    has_package_json: bool
    has_pyproject: bool
    has_requirements: bool
    has_dockerfile: bool
    npm_deps: list[str] = field(default_factory=list)
    pip_deps: list[str] = field(default_factory=list)


def scan_project_dir(d: Path) -> ProjectSignals:
    has_pkg = (d / "package.json").exists()
    has_pyp = (d / "pyproject.toml").exists()
    has_req = (d / "requirements.txt").exists()
    has_dock = (d / "Dockerfile").exists()

    npm_deps = parse_package_json_deps(d / "package.json") if has_pkg else []
    pip_deps = parse_requirements_txt(d / "requirements.txt") if has_req else []

    return ProjectSignals(
        has_package_json=has_pkg,
        has_pyproject=has_pyp,
        has_requirements=has_req,
        has_dockerfile=has_dock,
        npm_deps=npm_deps,
        pip_deps=pip_deps,
    )


def parse_dockerfile_installs(dockerfile: Path) -> dict[str, list[str]]:
    """Best-effort extract packages from common Dockerfile install patterns."""
    try:
        txt = dockerfile.read_text(encoding="utf-8", errors="ignore")
    except (FileNotFoundError, PermissionError):
        return {"apt": [], "apk": []}

    apt: list[str] = []
    apk: list[str] = []

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


_PROJECT_MARKERS = ("package.json", "pyproject.toml", "requirements.txt", "Dockerfile")
_SKIP_DIRS = {
    "node_modules", ".git", ".hg", "__pycache__", ".tox", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", "dist", "build", ".eggs",
}


def discover_projects(root: Path, max_depth: int = 5) -> list[Path]:
    """Walk *root* and return directories that contain project markers.

    Skips common non-project directories (node_modules, .git, etc.).
    Always includes *root* itself if it has markers.
    """
    found: list[Path] = []

    def _walk(d: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if any((d / m).exists() for m in _PROJECT_MARKERS):
            found.append(d)
        try:
            children = sorted(d.iterdir())
        except PermissionError:
            return
        for child in children:
            if child.is_dir() and child.name not in _SKIP_DIRS:
                _walk(child, depth + 1)

    _walk(root, 0)
    return found


def parse_requirements_txt(path: Path) -> list[str]:
    """Extract package names from a requirements.txt file."""
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except (FileNotFoundError, PermissionError):
        return []

    pkgs: list[str] = []
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[>=<!\[;@\s]", line)[0].strip()
        if name:
            pkgs.append(name)
    return pkgs


def parse_package_json_deps(path: Path) -> list[str]:
    """Extract dependency names from a package.json file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return []

    deps: list[str] = []
    for key in ("dependencies", "devDependencies"):
        section = data.get(key, {})
        if isinstance(section, dict):
            deps.extend(section.keys())
    return deps
