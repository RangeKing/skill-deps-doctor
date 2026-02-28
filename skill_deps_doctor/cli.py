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
    detect_playwright_runtime_need,
    scan_skills,
)
from .fix_gen import generate_fix_script
from .graph import build_graph, render_dot, render_platform_matrix, render_tree
from .hints import get_hint_db, init_hint_db, os_family
from .models import CheckContext, Finding
from .plugins import plugin_api_version, run_plugins, validate_plugins_contract
from .profiles import check_profile, list_profiles
from .snapshot import (
    build_snapshot,
    find_new_findings,
    load_baseline_findings,
    write_snapshot,
)
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
        prog="skill-deps-doctor",
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
    ap.add_argument(
        "--validate-hints",
        action="store_true",
        help="Validate merged hints schema (built-in + --hints-file) and exit",
    )
    ap.add_argument(
        "--validate-plugins",
        action="store_true",
        help="Validate plugin entry-point contracts and exit",
    )
    ap.add_argument(
        "--snapshot",
        default=None,
        metavar="PATH",
        help="Write a JSON snapshot (environment + findings) to PATH",
    )
    ap.add_argument(
        "--baseline",
        default=None,
        metavar="PATH",
        help="Compare current findings against a baseline JSON/snapshot file",
    )
    ap.add_argument(
        "--fail-on-new",
        action="store_true",
        help="With --baseline, fail if new warn/error findings are introduced",
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
    skills_dir = Path(args.skills_dir)

    # -- initialise hint DB ------------------------------------------------
    override = Path(args.hints_file) if args.hints_file else None
    db = init_hint_db(override)

    if args.validate_hints or args.validate_plugins:
        validation_findings: list[Finding] = []

        if args.validate_hints:
            errs = db.validation_errors
            if errs:
                for e in errs:
                    validation_findings.append(
                        Finding(
                            kind="hints_schema_invalid",
                            item=str(override) if override else "builtin:hints.yaml",
                            detail=e,
                            severity="error",
                            code="HINTS_SCHEMA_INVALID",
                            confidence="high",
                        )
                    )
            else:
                validation_findings.append(
                    Finding(
                        kind="hints_validation_info",
                        item=str(override) if override else "builtin:hints.yaml",
                        detail=(
                            f"HINTS OK (schema_version={db.schema_version}, "
                            f"expected={db.expected_schema_version})"
                        ),
                        severity="info",
                        code="HINTS_SCHEMA_OK",
                        confidence="high",
                    )
                )

        if args.validate_plugins:
            vctx = CheckContext(
                skills_dir=skills_dir,
                check_dir=Path(args.check_dir) if args.check_dir else None,
                probe=args.probe,
                profiles=args.profile,
                recursive=args.recursive,
                plugin_api_version=plugin_api_version(),
            )
            validation_findings.extend(validate_plugins_contract(vctx))

        issues = [f for f in validation_findings if f.severity in {"warn", "error"}]
        if issues:
            print("VALIDATION FAILED:")
        else:
            print("VALIDATION OK")
        for f in validation_findings:
            icon = _SEVERITY_ICON.get(f.severity, "\u2022")
            print(f"  {icon} [{f.kind}] {f.item}: {f.detail}")
        return 2 if issues else 0

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
    check_path = Path(args.check_dir) if args.check_dir else None
    playwright_reasons = detect_playwright_runtime_need(
        skills_dir=skills_dir,
        check_dir=check_path,
        profiles=args.profile,
    )

    findings: list[Finding] = []
    for err in get_hint_db().validation_errors:
        findings.append(
            Finding(
                kind="hints_schema_warning",
                item=str(override) if override else "builtin:hints.yaml",
                detail=err,
                severity="warn",
                code="HINTS_SCHEMA_INVALID",
                confidence="high",
            )
        )
    findings += check_bins(bins)
    findings += check_bin_versions(bin_specs)
    findings += check_install_arrays(installs)
    findings += check_fonts()
    findings += check_playwright_libs(
        enabled=bool(playwright_reasons),
        reason="; ".join(playwright_reasons),
    )

    if args.check_dir:
        assert check_path is not None
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
            plugin_api_version=plugin_api_version(),
        )
        findings += run_plugins(ctx)

    new_since_baseline: list[Finding] = []
    if args.baseline:
        baseline_path = Path(args.baseline)
        try:
            baseline_entries = load_baseline_findings(baseline_path)
        except ValueError as e:
            findings.append(
                Finding(
                    kind="baseline_invalid",
                    item=str(baseline_path),
                    detail=str(e),
                    severity="error",
                    code="BASELINE_INVALID",
                    confidence="high",
                )
            )
        else:
            new_since_baseline = find_new_findings(findings, baseline_entries)

    errors = [f for f in findings if f.severity == "error"]
    exit_code = 2 if errors else 0
    if args.fail_on_new and new_since_baseline:
        exit_code = 3

    if args.snapshot:
        snapshot_path = Path(args.snapshot)
        snapshot = build_snapshot(
            findings,
            skills_dir=skills_dir,
            check_dir=check_path,
            profiles=args.profile,
            probe=args.probe,
            recursive=args.recursive,
            no_plugins=args.no_plugins,
            hints_file=override,
            baseline_path=Path(args.baseline) if args.baseline else None,
            new_since_baseline=new_since_baseline if args.baseline else None,
        )
        write_snapshot(snapshot_path, snapshot)

    # -- platform matrix mode ----------------------------------------------
    if args.platform_matrix:
        print(render_platform_matrix(findings))
        if args.baseline and new_since_baseline and not args.quiet:
            print(f"\nBASELINE: {len(new_since_baseline)} new warn/error finding(s)")
        return exit_code

    # -- fix mode ----------------------------------------------------------
    if args.fix:
        print(generate_fix_script(findings))
        if args.baseline and new_since_baseline and not args.quiet:
            print(f"\nBASELINE: {len(new_since_baseline)} new warn/error finding(s)")
        return exit_code

    # -- json mode ---------------------------------------------------------
    if args.json_output:
        print(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2))
        return exit_code

    # -- human-readable output ---------------------------------------------
    display = _filter_by_verbosity(
        findings, quiet=args.quiet, verbose=args.verbose,
    )

    if not display:
        if not args.quiet:
            print("PASS: no obvious missing skill dependencies")
            if args.baseline:
                if new_since_baseline:
                    print(f"\nBASELINE: {len(new_since_baseline)} new warn/error finding(s)")
                else:
                    print("\nBASELINE: no new warn/error findings")
        return exit_code

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

    if args.baseline and not args.quiet:
        if new_since_baseline:
            print(f"\nBASELINE: {len(new_since_baseline)} new warn/error finding(s)")
            if args.verbose:
                for f in new_since_baseline:
                    print(f"  + [{f.severity}] [{f.kind}] {f.item}")
        else:
            print("\nBASELINE: no new warn/error findings")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
