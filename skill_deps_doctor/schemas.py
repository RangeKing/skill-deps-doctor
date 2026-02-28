from __future__ import annotations

from typing import Any

HINTS_SCHEMA_VERSION = 1
PLUGIN_API_VERSION = 1

_DICT_SECTIONS = (
    "bins",
    "libs",
    "fonts",
    "profiles",
    "package_deps",
    "version_commands",
    "transitive_deps",
)


def validate_hints_data(data: dict[str, Any]) -> list[str]:
    """Return schema validation errors for merged hints YAML content."""
    errors: list[str] = []

    schema_version = data.get("schema_version")
    if schema_version is None:
        errors.append("Missing top-level 'schema_version'")
    elif not isinstance(schema_version, int):
        errors.append("'schema_version' must be an integer")
    elif schema_version != HINTS_SCHEMA_VERSION:
        errors.append(
            f"Unsupported hints schema_version={schema_version} "
            f"(expected {HINTS_SCHEMA_VERSION})",
        )

    for key in _DICT_SECTIONS:
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            errors.append(f"Top-level '{key}' must be a mapping")

    package_deps = data.get("package_deps")
    if isinstance(package_deps, dict):
        for subkey in ("npm", "pip"):
            section = package_deps.get(subkey)
            if section is not None and not isinstance(section, dict):
                errors.append(f"'package_deps.{subkey}' must be a mapping")

    return errors
