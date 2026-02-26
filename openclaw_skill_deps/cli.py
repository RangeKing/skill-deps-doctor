from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Finding:
    kind: str
    item: str
    detail: str
    fix: str | None = None


BIN_HINTS = {
    "node": "Install Node.js (>=18) and npm",
    "npm": "Install Node.js (>=18) and npm",
    "uv": "Install uv: https://astral.sh/uv",
    "python": "Install Python 3.10+",
    "python3": "Install Python 3.10+",
    "ffmpeg": "sudo apt-get install -y ffmpeg",
    "pandoc": "sudo apt-get install -y pandoc",
    "git": "sudo apt-get install -y git",
}

APT_LIB_SUGGEST = {
    # Common Playwright/Chromium runtime deps (not exhaustive)
    "libnspr4.so": "sudo apt-get install -y libnspr4",
    "libnss3.so": "sudo apt-get install -y libnss3",
}

FONT_SUGGEST = {
    "Noto Sans CJK": "sudo apt-get install -y fonts-noto-cjk",
    "WenQuanYi": "sudo apt-get install -y fonts-wqy-zenhei fonts-wqy-microhei",
}


def which(name: str) -> str | None:
    return shutil.which(name)


def load_skill_requires(skill_md: Path) -> list[str]:
    """Parse SKILL.md frontmatter for metadata.clawdbot.requires.bins."""
    txt = skill_md.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"^---\n(.*?)\n---\n", txt, flags=re.S)
    if not m:
        return []
    fm = yaml.safe_load(m.group(1)) or {}
    md = (fm.get("metadata") or {}).get("clawdbot") or {}
    req = md.get("requires") or {}
    bins = req.get("bins") or []
    out: list[str] = []
    for b in bins:
        if isinstance(b, str):
            out.append(b)
    return out


def scan_skills(skills_dir: Path) -> list[str]:
    bins: set[str] = set()
    for p in skills_dir.glob("*/SKILL.md"):
        for b in load_skill_requires(p):
            bins.add(b)
    return sorted(bins)


def check_bins(bins: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for b in bins:
        if which(b) is None:
            findings.append(
                Finding(
                    kind="missing_bin",
                    item=b,
                    detail=f"Binary '{b}' not found in PATH",
                    fix=BIN_HINTS.get(b),
                )
            )
    return findings


def check_fonts() -> list[Finding]:
    # Best-effort: fontconfig presence and noto fonts.
    if which("fc-list") is None:
        return [
            Finding(
                kind="missing_bin",
                item="fc-list",
                detail="fontconfig not available; cannot verify fonts",
                fix="sudo apt-get install -y fontconfig",
            )
        ]

    out = subprocess.check_output(["fc-list"], text=True, errors="ignore")
    findings: list[Finding] = []
    if "NotoSansCJK" not in out and "Noto Sans CJK" not in out:
        findings.append(
            Finding(
                kind="missing_font",
                item="Noto Sans CJK",
                detail="CJK PDF export may show tofu (□) without CJK fonts",
                fix=FONT_SUGGEST["Noto Sans CJK"],
            )
        )
    return findings


def check_playwright_libs() -> list[Finding]:
    # Minimal heuristic: if playwright is installed in node_modules, check for a couple libs.
    # We don't attempt to run chromium here.
    findings: list[Finding] = []
    for so, fix in APT_LIB_SUGGEST.items():
        try:
            # `ldconfig -p` is common on Debian/Ubuntu.
            if which("ldconfig"):
                out = subprocess.check_output(["ldconfig", "-p"], text=True, errors="ignore")
                if so.replace(".so", "") not in out and so not in out:
                    findings.append(
                        Finding(
                            kind="missing_lib",
                            item=so,
                            detail=f"Likely required by Chromium/Playwright export",
                            fix=fix,
                        )
                    )
        except Exception:
            continue
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--check-dir", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    skills_dir = Path(args.skills_dir)
    bins = scan_skills(skills_dir)

    findings: list[Finding] = []
    findings += check_bins(bins)
    findings += check_fonts()
    findings += check_playwright_libs()

    if args.json:
        print(
            json.dumps(
                [f.__dict__ for f in findings], ensure_ascii=False, indent=2
            )
        )
        return 0 if not findings else 2

    if not findings:
        print("PASS: no obvious missing skill dependencies")
        return 0

    print("FAIL: missing dependencies detected\n")
    for f in findings:
        print(f"- [{f.kind}] {f.item}: {f.detail}")
        if f.fix:
            print(f"  Fix: {f.fix}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
