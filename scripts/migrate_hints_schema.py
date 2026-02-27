#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from openclaw_skill_deps.migration import migrate_hints_to_v1


def _load_yaml(path: Path) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"Failed to load YAML from {path}: {e}") from e
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SystemExit(f"YAML root in {path} must be a mapping")
    return raw


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="migrate_hints_schema.py",
        description="Migrate openclaw-skill-deps hints YAML to schema v1",
    )
    ap.add_argument("--in", dest="in_file", required=True, help="Input hints YAML path")
    ap.add_argument(
        "--out",
        dest="out_file",
        default=None,
        help="Output hints YAML path (default: overwrite input)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Check-only mode: exit 2 if migration is needed",
    )
    args = ap.parse_args()

    in_path = Path(args.in_file)
    out_path = Path(args.out_file) if args.out_file else in_path

    data = _load_yaml(in_path)
    migrated, changes = migrate_hints_to_v1(data)

    if args.check:
        if changes:
            print("MIGRATION REQUIRED:")
            for c in changes:
                print(f"  - {c}")
            return 2
        print("OK: no migration needed")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(migrated, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    if changes:
        print(f"Migrated hints schema and wrote: {out_path}")
        for c in changes:
            print(f"  - {c}")
    else:
        print(f"No changes needed. Wrote normalized file: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
