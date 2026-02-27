from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .hints import get_hint_db, os_family, which
from .models import Finding
from .parsers import parse_skill_md
from .scanners import discover_projects, parse_dockerfile_installs, scan_project_dir


def scan_skills(
    skills_dir: Path,
) -> tuple[list[str], list[tuple[Path, list[dict]]], list[str]]:
    """Return ``(required_bins, install_arrays_by_skill, bin_specs)``."""
    bins: set[str] = set()
    specs: list[str] = []
    installs: list[tuple[Path, list[dict]]] = []
    for p in skills_dir.glob("*/SKILL.md"):
        sm = parse_skill_md(p)
        for b in sm.bins:
            bins.add(b)
        specs.extend(sm.bin_specs)
        if sm.install:
            installs.append((p, sm.install))
    return sorted(bins), installs, specs


def check_bins(bins: list[str]) -> list[Finding]:
    db = get_hint_db()
    findings: list[Finding] = []
    for b in bins:
        if which(b) is None:
            findings.append(
                Finding(
                    kind="missing_bin",
                    item=b,
                    detail=f"Binary '{b}' not found in PATH",
                    fix=db.fix_for_bin(b),
                )
            )
    return findings


def check_fonts() -> list[Finding]:
    db = get_hint_db()

    if which("fc-list") is None:
        return [
            Finding(
                kind="missing_bin",
                item="fc-list",
                detail="fontconfig not available; cannot verify fonts",
                fix=db.fix_for_bin("fc-list"),
                severity="warn",
            )
        ]

    out = subprocess.check_output(["fc-list"], text=True, errors="ignore")
    findings: list[Finding] = []

    for font_name, entry in db.font_hints.items():
        patterns = db.fc_match_patterns(font_name)
        if not any(pat in out for pat in patterns):
            fix = db.fix_for_font(font_name)
            findings.append(
                Finding(
                    kind="missing_font",
                    item=font_name,
                    detail=f"CJK PDF export may show tofu (\u25a1) without '{font_name}'",
                    fix=fix,
                    severity="warn",
                )
            )

    return findings


def check_playwright_libs() -> list[Finding]:
    """Best-effort Playwright/Chromium shared-lib checks (Linux only)."""
    if os_family() != "linux":
        return []

    if which("ldconfig") is None:
        return []

    try:
        out = subprocess.check_output(["ldconfig", "-p"], text=True, errors="ignore")
    except Exception:
        return []

    db = get_hint_db()
    findings: list[Finding] = []
    for so, entry in db.lib_hints.items():
        if so.replace(".so", "") not in out and so not in out:
            findings.append(
                Finding(
                    kind="missing_lib",
                    item=so,
                    detail="Likely required by Chromium/Playwright export",
                    fix=entry.get("apt"),
                )
            )

    return findings


def check_install_arrays(installs: list[tuple[Path, list[dict]]]) -> list[Finding]:
    """Validate ``metadata.clawdbot.install`` arrays in SKILL.md."""
    db = get_hint_db()
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
                            fix=db.fix_for_bin(b),
                        )
                    )
    return findings


# ---------------------------------------------------------------------------
# Package-level dependency checks (npm / pip)
# ---------------------------------------------------------------------------


def check_package_deps(
    npm_deps: list[str], pip_deps: list[str]
) -> list[Finding]:
    """Cross-reference known npm/pip packages against system deps hints."""
    db = get_hint_db()
    findings: list[Finding] = []
    fam = os_family()

    for pkg in npm_deps:
        info = db.deps_for_npm_pkg(pkg)
        if info is None:
            continue
        note = info.get("note")
        apt = info.get("apt")
        fix = apt if fam == "linux" and apt else note
        findings.append(
            Finding(
                kind="package_dep_hint",
                item=f"npm:{pkg}",
                detail=note or f"Package '{pkg}' may need extra system deps",
                fix=fix,
                severity="warn",
            )
        )

    for pkg in pip_deps:
        info = db.deps_for_pip_pkg(pkg)
        if info is None:
            continue
        note = info.get("note")
        apt = info.get("apt")
        fix = apt if fam == "linux" and apt else note
        findings.append(
            Finding(
                kind="package_dep_hint",
                item=f"pip:{pkg}",
                detail=note or f"Package '{pkg}' may need extra system deps",
                fix=fix,
                severity="warn",
            )
        )

    return findings


def check_transitive_deps(
    npm_deps: list[str], pip_deps: list[str]
) -> list[Finding]:
    """Check transitive (indirect) library deps implied by npm/pip packages."""
    if os_family() != "linux":
        return []
    if which("ldconfig") is None:
        return []
    try:
        ldconfig_out = subprocess.check_output(
            ["ldconfig", "-p"], text=True, errors="ignore",
        )
    except Exception:
        return []

    db = get_hint_db()
    all_pkgs = list(npm_deps) + list(pip_deps)
    checked_libs: set[str] = set()
    findings: list[Finding] = []

    for pkg in all_pkgs:
        libs = db.transitive_libs(pkg)
        for so in libs:
            if so in checked_libs:
                continue
            checked_libs.add(so)
            if so.replace(".so", "") not in ldconfig_out and so not in ldconfig_out:
                findings.append(Finding(
                    kind="transitive_missing_lib",
                    item=so,
                    detail=f"Transitive dep of '{pkg}': {so} not found via ldconfig",
                    fix=db.fix_for_lib(so),
                ))

    return findings


# ---------------------------------------------------------------------------
# Playwright / Chromium probes (best-effort, opt-in via --probe)
# ---------------------------------------------------------------------------


def check_python_playwright(check_dir: Path, probe: bool) -> list[Finding]:
    """Detect Python Playwright — only probes when ``--probe`` is set."""
    findings: list[Finding] = []

    if not ((check_dir / "pyproject.toml").exists() or (check_dir / "requirements.txt").exists()):
        return findings

    if not probe:
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
        findings.append(
            Finding(
                kind="python_playwright_ok",
                item="python-playwright",
                detail=out,
                severity="info",
            )
        )
    except Exception as e:
        findings.append(
            Finding(
                kind="python_playwright_missing",
                item="python-playwright",
                detail=f"Python project detected but playwright import/version probe failed: {e}",
                fix="pip install playwright && python -m playwright install",
                severity="warn",
            )
        )

    return findings


def check_node_playwright(
    check_dir: Path, probe: bool
) -> tuple[list[Finding], Path | None]:
    """Cross-OS best-effort Node Playwright detection."""
    findings: list[Finding] = []
    pw_bin = check_dir / "node_modules" / ".bin" / (
        "playwright.cmd" if os_family() == "windows" else "playwright"
    )

    if not pw_bin.exists():
        return findings, None

    if probe:
        try:
            out = subprocess.check_output(
                [str(pw_bin), "--version"], text=True, errors="ignore", timeout=10
            )
            findings.append(
                Finding(
                    kind="playwright_ok",
                    item="playwright",
                    detail=out.strip(),
                    severity="info",
                )
            )
        except Exception as e:
            findings.append(
                Finding(
                    kind="playwright_probe_failed",
                    item="playwright",
                    detail=f"Found {pw_bin} but failed to run --version: {e}",
                    fix="Try reinstalling playwright (npm i -D playwright-chromium) and run npx playwright install",
                    severity="warn",
                )
            )
    else:
        findings.append(
            Finding(
                kind="playwright_found",
                item="playwright",
                detail=f"Found local playwright binary at {pw_bin} (probe disabled)",
                fix="Re-run with --probe to verify runtime",
                severity="info",
            )
        )

    return findings, pw_bin


def check_chromium_launch_smoke(check_dir: Path, probe: bool) -> list[Finding]:
    """Best-effort Chromium launch smoke test via Node Playwright."""
    if not probe:
        return []

    _, pw_bin = check_node_playwright(check_dir, probe=False)
    if not pw_bin:
        return []

    js = (
        "let pw; try { pw = require('playwright'); } catch(e) {"
        " try { pw = require('playwright-chromium'); } catch(e2) { throw e; } }"
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
                    severity="info",
                )
            )
        else:
            findings.append(
                Finding(
                    kind="chromium_launch_unknown",
                    item="chromium",
                    detail=out.strip()[:500],
                    severity="warn",
                )
            )
    except subprocess.CalledProcessError as e:
        msg = (e.output or "").strip()
        findings.append(
            Finding(
                kind="chromium_launch_failed",
                item="chromium",
                detail=f"Playwright chromium launch failed: {msg[:700]}",
                fix=(
                    "Install JS deps (npm i -D playwright-chromium) then run: "
                    "npx playwright install --with-deps (Linux) / npx playwright install (macOS/Windows)"
                ),
                severity="warn",
            )
        )
    except Exception as e:
        findings.append(
            Finding(
                kind="chromium_launch_failed",
                item="chromium",
                detail=f"Playwright chromium launch failed: {e}",
                fix=(
                    "Install JS deps (npm i -D playwright-chromium) then run: "
                    "npx playwright install --with-deps (Linux) / npx playwright install (macOS/Windows)"
                ),
                severity="warn",
            )
        )

    return findings


def check_projects_recursive(root: Path, probe: bool) -> list[Finding]:
    """Recursively discover sub-projects under *root* and check each."""
    findings: list[Finding] = []
    projects = discover_projects(root)

    if not projects:
        return findings

    for proj_dir in projects:
        rel = proj_dir.relative_to(root) if proj_dir != root else Path(".")
        sub = check_project_presets(proj_dir, probe)
        for f in sub:
            if str(rel) != ".":
                f.detail = f"[{rel}] {f.detail}"
        findings.extend(sub)

    return findings


def check_project_presets(check_dir: Path, probe: bool) -> list[Finding]:
    """Scan a project directory for Node/Python/Docker presets and probe."""
    sig = scan_project_dir(check_dir)
    needs: set[str] = set()
    findings: list[Finding] = []

    if sig.has_package_json:
        needs |= {"node", "npm"}

    if sig.has_pyproject or sig.has_requirements:
        needs |= {"python3"}

    if sig.has_dockerfile:
        needs |= {"docker"}
        pkgs = parse_dockerfile_installs(check_dir / "Dockerfile")
        if pkgs.get("apt"):
            findings.append(
                Finding(
                    kind="dockerfile_apt_packages",
                    item="Dockerfile",
                    detail=(
                        f"Detected apt-get packages: {' '.join(pkgs['apt'][:40])}"
                        + (" \u2026" if len(pkgs["apt"]) > 40 else "")
                    ),
                    severity="info",
                )
            )
        if pkgs.get("apk"):
            findings.append(
                Finding(
                    kind="dockerfile_apk_packages",
                    item="Dockerfile",
                    detail=(
                        f"Detected apk packages: {' '.join(pkgs['apk'][:40])}"
                        + (" \u2026" if len(pkgs["apk"]) > 40 else "")
                    ),
                    severity="info",
                )
            )

    findings += check_bins(sorted(needs))
    findings += check_package_deps(sig.npm_deps, sig.pip_deps)
    findings += check_transitive_deps(sig.npm_deps, sig.pip_deps)

    findings += check_python_playwright(check_dir, probe)
    node_findings, _ = check_node_playwright(check_dir, probe)
    findings += node_findings
    findings += check_chromium_launch_smoke(check_dir, probe)

    return findings
