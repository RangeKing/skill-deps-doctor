#!/usr/bin/env python3
from __future__ import annotations

# Thin wrapper so the ClawHub skill can run without editable installs.

import os
import sys
from pathlib import Path

# Add repo root (two levels up) to sys.path to import openclaw_skill_deps
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
sys.path.insert(0, str(REPO_ROOT))

from openclaw_skill_deps.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
