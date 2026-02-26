from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SkillMeta:
    name: str | None
    bins: list[str]
    install: list[dict]


def parse_skill_md(skill_md: Path) -> SkillMeta:
    txt = skill_md.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"^---\n(.*?)\n---\n", txt, flags=re.S)
    if not m:
        return SkillMeta(name=None, bins=[], install=[])

    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except Exception:
        # Some SKILL.md frontmatters are not strict YAML (e.g., unquoted colons).
        # Treat as unparseable instead of crashing the whole doctor run.
        return SkillMeta(name=None, bins=[], install=[])
    md = (fm.get("metadata") or {}).get("clawdbot") or {}

    req = md.get("requires") or {}
    bins = req.get("bins") or []
    out_bins = [b for b in bins if isinstance(b, str)]

    install = md.get("install") or []
    out_install = [x for x in install if isinstance(x, dict)]

    return SkillMeta(name=fm.get("name"), bins=out_bins, install=out_install)
