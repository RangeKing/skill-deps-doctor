#!/usr/bin/env python3
from __future__ import annotations

"""Thin wrapper for running openclaw-skill-deps from ClawHub skill context.

Behavior:
- If running inside this repository, add repo root to sys.path.
- Otherwise, rely on installed package (`pip install openclaw-skill-deps` or git URL).
- On import failure, print actionable install commands.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve()


def _inject_repo_root_if_present() -> None:
    # Expected repo layout: <root>/clawhub-skill/openclaw-skill-deps/scripts/...
    for candidate in (HERE.parents[3], HERE.parents[2], Path.cwd()):
        pkg_dir = candidate / "openclaw_skill_deps"
        if pkg_dir.is_dir():
            sys.path.insert(0, str(candidate))
            return


_inject_repo_root_if_present()

try:
    from openclaw_skill_deps.cli import main  # type: ignore[attr-defined]  # noqa: E402
except Exception as e:
    msg = (
        "Unable to import openclaw_skill_deps.\n"
        "Install it with one of:\n"
        "  pip install skill-deps-doctor\n"
        "  pip install openclaw-skill-deps\n"
        "  pip install \"git+https://github.com/RangeKing/openclaw-skill-deps.git\"\n"
        f"Import error: {e}"
    )
    print(msg, file=sys.stderr)
    raise SystemExit(2) from e


if __name__ == "__main__":
    raise SystemExit(main())
