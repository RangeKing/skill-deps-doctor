from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checkers import (
    check_bins,
    check_fonts,
    check_install_arrays,
    check_playwright_libs,
    check_project_presets,
    check_projects_recursive,
    check_transitive_deps,
    scan_skills,
)
from .fix_gen import generate_fix_script
from .graph import build_graph, render_dot, render_platform_matrix, render_tree
from .hints import init_hint_db, os_family
from .models import CheckContext, Finding
from .plugins import run_plugins
from .profiles import check_profile, list_profiles
from .versions import check_bin_versions

_SEVERITY_ICON = {"error": "[ERR]", "warn": "[WARN]", "info": "[INFO]"}


def _filter_by_verbosity(
    findings: list[Finding], *, quiet: bool, verbose: bool
) -> list[Finding]:
    if quiet:
        return [f for f in findings if f.severity == "error"]
    if verbose:
        return findings
    return [f for f in findings if f.severity != "info"]


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="openclaw-skill-deps",
        description="Skill-level dependency doctor for OpenClaw",
    )
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument(
        "--check-dir",
        default=None,
        help="Project/dir to scan for presets and package deps (Node/Python/Dockerfile)",
    )
    ap.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively discover sub-projects under --check-dir",
    )
    ap.add_argument(
        "--probe",
        action="store_true",
        help="Run lightweight probes (e.g. playwright --version)",
    )
    ap.add_argument(
        "--profile",
        action="append",
        default=[],
        metavar="NAME",
        help="Check deps for a named profile (repeatable). Use --list-profiles to see options.",
    )
    ap.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available dependency profiles and exit",
    )
    ap.add_argument(
        "--fix",
        action="store_true",
        help="Output a fix script (bash/PowerShell) to stdout instead of the report",
    )
    ap.add_argument(
        "--hints-file",
        default=None,
        metavar="PATH",
        help="YAML file with custom/override hint entries",
    )
    ap.add_argument(
        "--no-plugins",
        action="store_true",
        help="Disable third-party checker plugins",
    )
    ap.add_argument(
        "--graph",
        choices=["tree", "dot"],
        default=None,
        metavar="FORMAT",
        help="Output dependency graph (tree or dot) instead of the report",
    )
    ap.add_argument(
        "--platform-matrix",
        action="store_true",
        help="Display a multi-platform fix matrix for all actionable findings",
    )

    verbosity = ap.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose", action="store_true", help="Show all findings including info",
    )
    verbosity.add_argument(
        "-q", "--quiet", action="store_true", help="Show only errors",
    )

    ap.add_argument("--json", dest="json_output", action="store_true")
    args = ap.parse_args()

    # -- initialise hint DB ------------------------------------------------
    override = Path(args.hints_file) if args.hints_file else None
    init_hint_db(override)

    # -- list-profiles (early exit) ----------------------------------------
    if args.list_profiles:
        profiles = list_profiles()
        if not profiles:
            print("No profiles available.")
            return 0
        max_name = max(len(n) for n, _ in profiles)
        for name, desc in profiles:
            print(f"  {name:<{max_name}}  {desc}")
        return 0

    # -- graph mode (early exit) -------------------------------------------
    skills_dir = Path(args.skills_dir)
    if args.graph:
        check_path = Path(args.check_dir) if args.check_dir else None
        roots = build_graph(skills_dir, check_path)
        if args.graph == "dot":
            print(render_dot(roots))
        else:
            print(render_tree(roots))
        return 0

    # -- collect findings --------------------------------------------------
    bins, installs, bin_specs = scan_skills(skills_dir)

    findings: list[Finding] = []
    findings += check_bins(bins)
    findings += check_bin_versions(bin_specs)
    findings += check_install_arrays(installs)
    findings += check_fonts()
    findings += check_playwright_libs()

    if args.check_dir:
        check_path = Path(args.check_dir)
        if args.recursive:
            findings += check_projects_recursive(check_path, probe=args.probe)
        else:
            findings += check_project_presets(check_path, probe=args.probe)

    for prof in args.profile:
        findings += check_profile(prof)

    # -- plugins -----------------------------------------------------------
    if not args.no_plugins:
        ctx = CheckContext(
            skills_dir=skills_dir,
            check_dir=Path(args.check_dir) if args.check_dir else None,
            probe=args.probe,
            profiles=args.profile,
            recursive=args.recursive,
        )
        findings += run_plugins(ctx)

    errors = [f for f in findings if f.severity == "error"]

    # -- platform matrix mode ----------------------------------------------
    if args.platform_matrix:
        print(render_platform_matrix(findings))
        return 2 if errors else 0

    # -- fix mode ----------------------------------------------------------
    if args.fix:
        print(generate_fix_script(findings))
        return 2 if errors else 0

    # -- json mode ---------------------------------------------------------
    if args.json_output:
        print(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2))
        return 2 if errors else 0

    # -- human-readable output ---------------------------------------------
    display = _filter_by_verbosity(
        findings, quiet=args.quiet, verbose=args.verbose,
    )

    if not display:
        if not args.quiet:
            print("PASS: no obvious missing skill dependencies")
        return 2 if errors else 0

    if errors:
        print(f"FAIL: {len(errors)} error(s) detected\n")
    else:
        print(f"OK: {len(display)} info/warning(s), no errors\n")

    if args.verbose:
        print(f"OS: {os_family()}\n")

    for f in display:
        icon = _SEVERITY_ICON.get(f.severity, "\u2022")
        print(f"  {icon} [{f.kind}] {f.item}: {f.detail}")
        if f.fix:
            print(f"    Fix: {f.fix}")

    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
