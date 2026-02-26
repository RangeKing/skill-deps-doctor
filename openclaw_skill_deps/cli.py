from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Finding:
    kind: str
    item: str
    detail: str
    fix: str | None = None


def os_family() -> str:
    p = sys.platform
    if p.startswith("linux"):
        return "linux"
    if p == "darwin":
        return "macos"
    if p.startswith("win"):
        return "windows"
    return "other"


def fix_for_bin(bin_name: str) -> str | None:
    """Return a best-effort install hint for a binary across major OSes."""
    fam = os_family()

    # Cross-platform hints
    if bin_name in {"node", "npm"}:
        if fam == "windows":
            return "Install Node.js (LTS) or: choco install nodejs-lts"
        if fam == "macos":
            return "Install Node.js (LTS) or: brew install node"
        return "Install Node.js (>=18) and npm"

    if bin_name == "uv":
        return "Install uv: https://astral.sh/uv"

    if bin_name in {"python", "python3"}:
        if fam == "windows":
            return "Install Python 3.10+ from python.org or: choco install python"
        if fam == "macos":
            return "Install Python 3.10+ or: brew install python"
        return "Install Python 3.10+"

    if bin_name == "git":
        if fam == "windows":
            return "Install Git for Windows or: choco install git"
        if fam == "macos":
            return "Install Xcode Command Line Tools or: brew install git"
        return "sudo apt-get install -y git"

    if bin_name == "ffmpeg":
        if fam == "windows":
            return "Install ffmpeg or: choco install ffmpeg"
        if fam == "macos":
            return "brew install ffmpeg"
        return "sudo apt-get install -y ffmpeg"

    if bin_name == "pandoc":
        if fam == "windows":
            return "Install pandoc or: choco install pandoc"
        if fam == "macos":
            return "brew install pandoc"
        return "sudo apt-get install -y pandoc"

    if bin_name == "docker":
        if fam == "windows":
            return "Install Docker Desktop"
        if fam == "macos":
            return "Install Docker Desktop"
        return "Install docker engine (e.g. sudo apt-get install -y docker.io)"

    if bin_name == "fc-list":
        if fam == "linux":
            return "sudo apt-get install -y fontconfig"
        return "Install fontconfig"

    return None

APT_LIB_SUGGEST = {
    # Common Playwright/Chromium runtime deps (Linux). Not exhaustive.
    "libnspr4.so": "sudo apt-get install -y libnspr4",
    "libnss3.so": "sudo apt-get install -y libnss3",
}

FONT_SUGGEST = {
    # CJK fonts
    "Noto Sans CJK": {
        "linux": "sudo apt-get install -y fonts-noto-cjk",
        "macos": "brew install --cask font-noto-sans-cjk-sc  # or install via system font book",
        "windows": "Install Noto Sans CJK (ttf/otf) or a CJK font pack; then rerun fc-cache",
    },
    "WenQuanYi": {
        "linux": "sudo apt-get install -y fonts-wqy-zenhei fonts-wqy-microhei",
        "macos": None,
        "windows": None,
    },
}


def which(name: str) -> str | None:
    return shutil.which(name)


def load_skill_requires(skill_md: Path) -> list[str]:
    """Parse SKILL.md frontmatter for metadata.clawdbot.requires.bins.

    Note: some skills also provide `metadata.clawdbot.install` (official install hints).
    We validate those separately.
    """
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


from .parsers import parse_skill_md
from .scanners import scan_project_dir, parse_dockerfile_installs


def scan_skills(skills_dir: Path) -> tuple[list[str], list[tuple[Path, list[dict]]]]:
    """Return (required_bins, install_arrays_by_skill)."""
    bins: set[str] = set()
    installs: list[tuple[Path, list[dict]]] = []
    for p in skills_dir.glob("*/SKILL.md"):
        sm = parse_skill_md(p)
        for b in sm.bins:
            bins.add(b)
        if sm.install:
            installs.append((p, sm.install))
    return sorted(bins), installs


def check_bins(bins: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for b in bins:
        if which(b) is None:
            findings.append(
                Finding(
                    kind="missing_bin",
                    item=b,
                    detail=f"Binary '{b}' not found in PATH",
                    fix=fix_for_bin(b),
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
                fix=fix_for_bin("fc-list"),
            )
        ]

    out = subprocess.check_output(["fc-list"], text=True, errors="ignore")
    findings: list[Finding] = []

    fam = os_family()
    noto_fix = (FONT_SUGGEST.get("Noto Sans CJK") or {}).get(fam)

    if "NotoSansCJK" not in out and "Noto Sans CJK" not in out:
        findings.append(
            Finding(
                kind="missing_font",
                item="Noto Sans CJK",
                detail="CJK PDF export may show tofu (□) without CJK fonts",
                fix=noto_fix,
            )
        )

    return findings


def check_playwright_libs() -> list[Finding]:
    """Best-effort Playwright/Chromium runtime dependency checks.

    Today we only do Linux shared-lib heuristics. macOS/Windows are skipped.
    """
    if os_family() != "linux":
        return []

    findings: list[Finding] = []
    if which("ldconfig") is None:
        # Can't validate shared libs without ldconfig.
        return []

    try:
        out = subprocess.check_output(["ldconfig", "-p"], text=True, errors="ignore")
    except Exception:
        return []

    for so, fix in APT_LIB_SUGGEST.items():
        if so.replace(".so", "") not in out and so not in out:
            findings.append(
                Finding(
                    kind="missing_lib",
                    item=so,
                    detail="Likely required by Chromium/Playwright export",
                    fix=fix,
                )
            )

    return findings


def check_install_arrays(installs: list[tuple[Path, list[dict]]]) -> list[Finding]:
    """Validate `metadata.clawdbot.install` arrays in SKILL.md.

    For entries that declare `bins`, we verify those binaries exist. We do NOT auto-install.
    """
    findings: list[Finding] = []
    for skill_path, arr in installs:
        for entry in arr:
            bins = entry.get("bins") or []
            if not isinstance(bins, list):
                continue
            for b in bins:
                if not isinstance(b, str):
                    continue
                if which(b) is None:
                    label = entry.get("label") or entry.get("id") or "install"
                    findings.append(
                        Finding(
                            kind="missing_install_bin",
                            item=b,
                            detail=f"{skill_path.parent.name}: install hint '{label}' expects bin '{b}'",
                            fix=fix_for_bin(b),
                        )
                    )
    return findings


def check_python_playwright(check_dir: Path, probe: bool) -> list[Finding]:
    """Detect Python Playwright (best-effort).

    We don't create venvs. We only probe the current Python interpreter.
    """
    findings: list[Finding] = []

    # Only relevant if this looks like a Python project
    if not ((check_dir / "pyproject.toml").exists() or (check_dir / "requirements.txt").exists()):
        return findings

    if not probe:
        # Don't import modules unless user asks.
        return findings

    try:
        out = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "import playwright; import importlib.metadata as m; print('python-playwright', m.version('playwright'))",
            ],
            text=True,
            errors="ignore",
            timeout=10,
        ).strip()
        findings.append(Finding(kind="python_playwright_ok", item="python-playwright", detail=out))
    except Exception as e:
        findings.append(
            Finding(
                kind="python_playwright_missing",
                item="python-playwright",
                detail=f"Python project detected but playwright import/version probe failed: {e}",
                fix="pip install playwright && python -m playwright install",
            )
        )

    return findings


def check_node_playwright(check_dir: Path, probe: bool) -> tuple[list[Finding], Path | None]:
    """Cross-OS best-effort Node Playwright detection.

    Returns (findings, playwright_bin_path).
    """
    findings: list[Finding] = []
    pw_bin = check_dir / "node_modules" / ".bin" / ("playwright.cmd" if os_family() == "windows" else "playwright")

    if not pw_bin.exists():
        return findings, None

    if probe:
        try:
            out = subprocess.check_output([str(pw_bin), "--version"], text=True, errors="ignore", timeout=10)
            findings.append(Finding(kind="playwright_ok", item="playwright", detail=out.strip()))
        except Exception as e:
            findings.append(
                Finding(
                    kind="playwright_probe_failed",
                    item="playwright",
                    detail=f"Found {pw_bin} but failed to run --version: {e}",
                    fix="Try reinstalling playwright (npm i -D playwright-chromium) and run npx playwright install",
                )
            )
    else:
        findings.append(
            Finding(
                kind="playwright_found",
                item="playwright",
                detail=f"Found local playwright binary at {pw_bin} (probe disabled)",
                fix="Re-run with --probe to verify runtime",
            )
        )

    return findings, pw_bin


def check_chromium_launch_smoke(check_dir: Path, probe: bool) -> list[Finding]:
    """Best-effort Chromium launch smoke test via Node Playwright.

    This catches: browser not installed, missing system deps, sandbox issues.
    """
    if not probe:
        return []

    # Only attempt if Node Playwright exists
    _, pw_bin = check_node_playwright(check_dir, probe=False)
    if not pw_bin:
        return []

    # Use node script that prefers local package resolution.
    js = (
        "let pw; try { pw = require('playwright'); } catch(e) { try { pw = require('playwright-chromium'); } catch(e2) { throw e; } }"
        "; const { chromium } = pw;"
        "(async()=>{const b=await chromium.launch({headless:true});"
        "const p=await b.newPage(); await p.goto('about:blank');"
        "await b.close(); console.log('chromium_launch_ok');})().catch(e=>{"
        "console.error('chromium_launch_failed'); console.error(String(e)); process.exit(2);});"
    )

    findings: list[Finding] = []
    try:
        out = subprocess.check_output(
            ["node", "-e", js],
            cwd=str(check_dir),
            text=True,
            errors="ignore",
            timeout=15,
            stderr=subprocess.STDOUT,
        )
        if "chromium_launch_ok" in out:
            findings.append(
                Finding(
                    kind="chromium_launch_ok",
                    item="chromium",
                    detail="Chromium launched successfully via Playwright",
                )
            )
        else:
            findings.append(Finding(kind="chromium_launch_unknown", item="chromium", detail=out.strip()[:500]))
    except subprocess.CalledProcessError as e:
        msg = (e.output or "").strip()
        findings.append(
            Finding(
                kind="chromium_launch_failed",
                item="chromium",
                detail=f"Playwright chromium launch failed: {msg[:700]}",
                fix="Install JS deps (npm i -D playwright-chromium) then run: npx playwright install --with-deps (Linux) / npx playwright install (macOS/Windows)",
            )
        )
    except Exception as e:
        findings.append(
            Finding(
                kind="chromium_launch_failed",
                item="chromium",
                detail=f"Playwright chromium launch failed: {e}",
                fix="Install JS deps (npm i -D playwright-chromium) then run: npx playwright install --with-deps (Linux) / npx playwright install (macOS/Windows)",
            )
        )

    return findings


def check_project_presets(check_dir: Path, probe: bool) -> list[Finding]:
    sig = scan_project_dir(check_dir)
    needs: set[str] = set()
    findings: list[Finding] = []

    # Node preset
    if sig.has_package_json:
        needs |= {"node", "npm"}

    # Python preset
    if sig.has_pyproject or sig.has_requirements:
        needs |= {"python3"}

    # Docker preset
    if sig.has_dockerfile:
        needs |= {"docker"}
        # Parse Dockerfile packages for hints
        pkgs = parse_dockerfile_installs(check_dir / "Dockerfile")
        if pkgs.get("apt"):
            findings.append(
                Finding(
                    kind="dockerfile_apt_packages",
                    item="Dockerfile",
                    detail=f"Detected apt-get packages: {' '.join(pkgs['apt'][:40])}" + (" …" if len(pkgs['apt'])>40 else ""),
                    fix=None,
                )
            )
        if pkgs.get("apk"):
            findings.append(
                Finding(
                    kind="dockerfile_apk_packages",
                    item="Dockerfile",
                    detail=f"Detected apk packages: {' '.join(pkgs['apk'][:40])}" + (" …" if len(pkgs['apk'])>40 else ""),
                    fix=None,
                )
            )

    findings += check_bins(sorted(needs))

    # Probes
    findings += check_python_playwright(check_dir, probe)
    node_findings, _ = check_node_playwright(check_dir, probe)
    findings += node_findings
    findings += check_chromium_launch_smoke(check_dir, probe)

    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--check-dir", default=None, help="Optional project/dir to scan for presets (Node/Python/Dockerfile)")
    ap.add_argument("--probe", action="store_true", help="Run lightweight probes (e.g. playwright --version) when possible")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    skills_dir = Path(args.skills_dir)
    bins, installs = scan_skills(skills_dir)

    findings: list[Finding] = []
    findings += check_bins(bins)
    findings += check_install_arrays(installs)
    findings += check_fonts()
    findings += check_playwright_libs()

    if args.check_dir:
        findings += check_project_presets(Path(args.check_dir), probe=args.probe)

    if args.json:
        print(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2))
        return 0 if not findings else 2

    if not findings:
        print("PASS: no obvious missing skill dependencies")
        return 0

    print("FAIL: missing dependencies detected\n")
    print(f"OS: {os_family()}\n")
    for f in findings:
        print(f"- [{f.kind}] {f.item}: {f.detail}")
        if f.fix:
            print(f"  Fix: {f.fix}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
