from __future__ import annotations

from copy import deepcopy
from typing import Any

from .schemas import HINTS_SCHEMA_VERSION

_TOP_LEVEL_MAP_KEYS = (
    "bins",
    "libs",
    "fonts",
    "profiles",
    "package_deps",
    "version_commands",
    "transitive_deps",
)


def migrate_hints_to_v1(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Migrate a hints object to schema v1 and return (migrated, changes)."""
    out = deepcopy(data)
    changes: list[str] = []

    if out.get("schema_version") != HINTS_SCHEMA_VERSION:
        out["schema_version"] = HINTS_SCHEMA_VERSION
        changes.append(f"Set schema_version={HINTS_SCHEMA_VERSION}")

    for key in _TOP_LEVEL_MAP_KEYS:
        value = out.get(key)
        if value is None:
            out[key] = {}
            changes.append(f"Added missing top-level map '{key}'")
        elif not isinstance(value, dict):
            out[key] = {}
            changes.append(f"Reset non-mapping '{key}' to empty mapping")

    pkg = out.get("package_deps", {})
    if not isinstance(pkg, dict):
        pkg = {}
        out["package_deps"] = pkg
        changes.append("Reset non-mapping 'package_deps' to empty mapping")

    for sub in ("npm", "pip"):
        section = pkg.get(sub)
        if section is None:
            pkg[sub] = {}
            changes.append(f"Added missing package_deps.{sub} mapping")
        elif not isinstance(section, dict):
            pkg[sub] = {}
            changes.append(f"Reset non-mapping package_deps.{sub} to empty mapping")

    return out, changes


def migration_needed(data: dict[str, Any]) -> bool:
    """Return True when input data would change after migration."""
    migrated, _changes = migrate_hints_to_v1(data)
    return migrated != data
