from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SkillMeta:
    name: str | None
    bins: list[str]
    install: list[dict]
    bin_specs: list[str] = field(default_factory=list)


def parse_skill_md(skill_md: Path) -> SkillMeta:
    txt = skill_md.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"^---\n(.*?)\n---\n", txt, flags=re.S)
    if not m:
        return SkillMeta(name=None, bins=[], install=[])

    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except Exception:
        return SkillMeta(name=None, bins=[], install=[])
    md = (fm.get("metadata") or {}).get("clawdbot") or {}

    req = md.get("requires") or {}
    raw_bins = req.get("bins") or []
    specs = [b for b in raw_bins if isinstance(b, str)]
    bare_names = [re.split(r"[><=!]", b)[0] for b in specs]

    install = md.get("install") or []
    out_install = [x for x in install if isinstance(x, dict)]

    return SkillMeta(
        name=fm.get("name"),
        bins=bare_names,
        install=out_install,
        bin_specs=specs,
    )
