from __future__ import annotations

import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from .schemas import HINTS_SCHEMA_VERSION, validate_hints_data

_DATA_DIR = Path(__file__).parent / "data"

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def os_family() -> str:
    p = sys.platform
    if p.startswith("linux"):
        return "linux"
    if p == "darwin":
        return "macos"
    if p.startswith("win"):
        return "windows"
    return "other"


def which(name: str) -> str | None:
    return shutil.which(name)


# ---------------------------------------------------------------------------
# Command extraction (used by fix_gen)
# ---------------------------------------------------------------------------

_COMMAND_PREFIXES = (
    "sudo ",
    "apt-get ",
    "apt ",
    "brew ",
    "choco ",
    "pip ",
    "pip3 ",
    "npm ",
    "npx ",
    "curl ",
    "wget ",
    "xcode-select ",
)

_APT_INSTALL_RE = re.compile(r"^(?:sudo\s+)?(?:apt-get|apt)\s+install(?:\s+-y)?\s+(.+)$")


def extract_cmd(fix: str) -> str | None:
    """Return the runnable portion of a fix hint, or *None* for manual steps."""
    fix = fix.strip()
    if fix.startswith(("(", "Install ", "Binary ")):
        return None
    for prefix in _COMMAND_PREFIXES:
        if fix.startswith(prefix):
            return fix
    return None


def detect_linux_pkg_manager() -> str | None:
    """Best-effort detect the Linux package manager available on this host."""
    if os_family() != "linux":
        return None

    distro_tags = _linux_distro_tags()
    preferred: list[str] = []
    if any(x in distro_tags for x in ("debian", "ubuntu", "mint", "kali", "pop")):
        preferred = ["apt-get", "apt"]
    elif any(x in distro_tags for x in ("fedora", "rhel", "centos", "rocky", "almalinux", "amzn")):
        preferred = ["dnf", "yum"]
    elif any(x in distro_tags for x in ("alpine",)):
        preferred = ["apk"]
    elif any(x in distro_tags for x in ("arch", "manjaro")):
        preferred = ["pacman"]

    candidates = preferred + ["apt-get", "apt", "dnf", "yum", "apk", "pacman"]
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        if which(name):
            return name
    return None


def _linux_distro_tags() -> set[str]:
    path = Path("/etc/os-release")
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return set()

    values: list[str] = []
    for line in txt.splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        key = key.strip()
        if key not in {"ID", "ID_LIKE"}:
            continue
        values.append(raw.strip().strip('"').strip("'").lower())

    tags: set[str] = set()
    for value in values:
        tags.update(x for x in value.split() if x)
    return tags


def _extract_packages_from_apt_install(expr: str) -> str:
    try:
        tokens = shlex.split(expr)
    except ValueError:
        return ""
    packages = [t for t in tokens if t and not t.startswith("-")]
    return " ".join(packages)


def _adapt_linux_install_hint(cmd: str) -> str:
    """Rewrite apt/apt-get install hints for the host Linux package manager."""
    m = _APT_INSTALL_RE.match(cmd.strip())
    if not m:
        return cmd

    packages = _extract_packages_from_apt_install(m.group(1))
    if not packages:
        return cmd

    manager = detect_linux_pkg_manager()
    if manager in ("apt-get", "apt"):
        return f"sudo {manager} install -y {packages}"
    if manager == "dnf":
        return f"sudo dnf install -y {packages}"
    if manager == "yum":
        return f"sudo yum install -y {packages}"
    if manager == "apk":
        return f"sudo apk add --no-cache {packages}"
    if manager == "pacman":
        return f"sudo pacman -S --needed --noconfirm {packages}"
    return cmd


# ---------------------------------------------------------------------------
# HintDB — loads hints.yaml (+ optional user overrides)
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


class HintDB:
    """Hint database backed by YAML with optional user overrides."""

    def __init__(self, override_path: Path | None = None) -> None:
        base = _load_yaml(_DATA_DIR / "hints.yaml")
        if override_path:
            user = _load_yaml(override_path)
            if "schema_version" in user:
                base["schema_version"] = user["schema_version"]
            merge_keys = (
                "bins", "libs", "fonts", "profiles", "package_deps",
                "version_commands", "transitive_deps",
            )
            for key in merge_keys:
                if key in user:
                    base.setdefault(key, {}).update(user[key])

        self._schema_version: int | None = (
            base.get("schema_version")
            if isinstance(base.get("schema_version"), int)
            else None
        )
        self._validation_errors = validate_hints_data(base)

        self._bins: dict[str, dict[str, str]] = base.get("bins", {})
        self._libs: dict[str, dict[str, str]] = base.get("libs", {})
        self._fonts: dict[str, dict[str, Any]] = base.get("fonts", {})
        self._profiles: dict[str, dict[str, Any]] = base.get("profiles", {})
        self._package_deps: dict[str, dict[str, dict[str, str]]] = base.get("package_deps", {})
        self._version_cmds: dict[str, dict[str, str]] = base.get("version_commands", {})
        self._transitive: dict[str, dict[str, Any]] = base.get("transitive_deps", {})

    # -- bin hints ---------------------------------------------------------

    def _resolve_bin(self, name: str, depth: int = 0) -> dict[str, str] | None:
        if depth > 5:
            return None
        entry = self._bins.get(name)
        if entry is None:
            return None
        alias = entry.get("_alias")
        if alias and isinstance(alias, str):
            return self._resolve_bin(alias, depth + 1)
        return entry

    def fix_for_bin(self, bin_name: str) -> str | None:
        entry = self._resolve_bin(bin_name)
        fam = os_family()
        if entry is None:
            return self._generic_bin_hint(bin_name)
        hint = entry.get(fam) or entry.get("_all") or self._generic_bin_hint(bin_name)
        return self.normalize_fix_command(hint, family=fam)

    @staticmethod
    def _generic_bin_hint(bin_name: str) -> str:
        fam = os_family()
        parts = [f"'{bin_name}' not in hint database"]
        if fam == "linux":
            parts.append(f"try: apt-cache search {bin_name}")
        elif fam == "macos":
            parts.append(f"try: brew search {bin_name}")
        elif fam == "windows":
            parts.append(f"try: choco search {bin_name}")
        return "; ".join(parts)

    # -- lib hints ---------------------------------------------------------

    @property
    def lib_hints(self) -> dict[str, dict[str, str]]:
        return self._libs

    def fix_for_lib(self, lib_name: str) -> str | None:
        entry = self._libs.get(lib_name)
        if entry is None:
            return None
        return self.normalize_fix_command(entry.get("apt"), family="linux")

    # -- font hints --------------------------------------------------------

    @property
    def font_hints(self) -> dict[str, dict[str, Any]]:
        return self._fonts

    def fix_for_font(self, font_name: str) -> str | None:
        entry = self._fonts.get(font_name)
        if entry is None:
            return None
        fam = os_family()
        return self.normalize_fix_command(entry.get(fam), family=fam)

    def fc_match_patterns(self, font_name: str) -> list[str]:
        entry = self._fonts.get(font_name)
        if entry is None:
            return [font_name]
        patterns: list[str] = entry.get("fc_match", [font_name])
        return patterns

    # -- profiles ----------------------------------------------------------

    @property
    def profiles(self) -> dict[str, dict[str, Any]]:
        return self._profiles

    # -- package deps ------------------------------------------------------

    @property
    def package_deps(self) -> dict[str, dict[str, dict[str, str]]]:
        return self._package_deps

    def deps_for_npm_pkg(self, pkg: str) -> dict[str, str] | None:
        return self._package_deps.get("npm", {}).get(pkg)

    def deps_for_pip_pkg(self, pkg: str) -> dict[str, str] | None:
        return self._package_deps.get("pip", {}).get(pkg)

    # -- version commands --------------------------------------------------

    def version_command(self, bin_name: str) -> dict[str, str] | None:
        return self._version_cmds.get(bin_name)

    # -- transitive deps ---------------------------------------------------

    def _resolve_transitive(self, name: str, depth: int = 0) -> dict[str, Any] | None:
        if depth > 5:
            return None
        entry = self._transitive.get(name)
        if entry is None:
            return None
        alias = entry.get("_alias")
        if alias and isinstance(alias, str):
            return self._resolve_transitive(alias, depth + 1)
        return entry

    def transitive_libs(self, pkg_name: str) -> list[str]:
        """Return transitive Linux shared-lib deps for *pkg_name*, or ``[]``."""
        entry = self._resolve_transitive(pkg_name)
        if entry is None:
            return []
        libs: list[str] = entry.get("libs_linux", [])
        return libs

    def all_bin_fixes(self, bin_name: str) -> dict[str, str | None]:
        """Return fix hints for *all* platforms (for matrix output)."""
        entry = self._resolve_bin(bin_name)
        platforms = {}
        for fam in ("linux", "macos", "windows"):
            if entry:
                hint = entry.get(fam) or entry.get("_all")
                platforms[fam] = self.normalize_fix_command(hint, family=fam)
            else:
                platforms[fam] = self._generic_bin_hint_for(bin_name, fam)
        return platforms

    def normalize_fix_command(
        self, fix: str | None, *, family: str | None = None,
    ) -> str | None:
        """Normalize fix command text to host platform conventions when possible."""
        if fix is None:
            return None
        fam = family or os_family()
        if fam == "linux":
            return _adapt_linux_install_hint(fix)
        return fix

    @property
    def schema_version(self) -> int | None:
        return self._schema_version

    @property
    def expected_schema_version(self) -> int:
        return HINTS_SCHEMA_VERSION

    @property
    def validation_errors(self) -> list[str]:
        return list(self._validation_errors)

    @staticmethod
    def _generic_bin_hint_for(bin_name: str, fam: str) -> str:
        parts = [f"'{bin_name}' not in hint database"]
        if fam == "linux":
            parts.append(f"try: apt-cache search {bin_name}")
        elif fam == "macos":
            parts.append(f"try: brew search {bin_name}")
        elif fam == "windows":
            parts.append(f"try: choco search {bin_name}")
        return "; ".join(parts)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_hint_db: HintDB | None = None


def init_hint_db(override_path: Path | None = None) -> HintDB:
    """(Re)initialise the global HintDB.  Call once from CLI startup."""
    global _hint_db
    _hint_db = HintDB(override_path)
    return _hint_db


def get_hint_db() -> HintDB:
    """Return the global HintDB, creating a default one if needed."""
    global _hint_db
    if _hint_db is None:
        _hint_db = HintDB()
    return _hint_db


def reset_hint_db() -> None:
    """Clear the cached singleton (useful in tests)."""
    global _hint_db
    _hint_db = None


# ---------------------------------------------------------------------------
# Backward-compatible module-level helper
# ---------------------------------------------------------------------------


def fix_for_bin(bin_name: str) -> str | None:
    return get_hint_db().fix_for_bin(bin_name)


def normalize_fix_command(fix: str | None) -> str | None:
    return get_hint_db().normalize_fix_command(fix)
