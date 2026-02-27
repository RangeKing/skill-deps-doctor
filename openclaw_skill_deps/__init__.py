from __future__ import annotations

from pathlib import Path

from .models import CheckContext, Finding

__all__ = ["Finding", "CheckContext", "run_check"]


def run_check(
    skills_dir: str | Path,
    *,
    check_dir: str | Path | None = None,
    profiles: list[str] | None = None,
    probe: bool = False,
    recursive: bool = False,
    hints_file: str | Path | None = None,
    use_plugins: bool = True,
) -> list[Finding]:
    """Programmatic entry point — run all checks and return findings.

    Designed for embedding in other tools (e.g. ``openclaw doctor``).

    Example::

        from openclaw_skill_deps import run_check

        findings = run_check("./skills", check_dir=".", profiles=["slidev"])
        errors = [f for f in findings if f.severity == "error"]
    """
    from .checkers import (
        check_bins,
        check_fonts,
        check_install_arrays,
        check_playwright_libs,
        check_project_presets,
        check_projects_recursive,
        scan_skills,
    )
    from .hints import init_hint_db
    from .plugins import run_plugins
    from .profiles import check_profile
    from .versions import check_bin_versions

    override = Path(hints_file) if hints_file else None
    init_hint_db(override)

    ctx = CheckContext(
        skills_dir=Path(skills_dir),
        check_dir=Path(check_dir) if check_dir else None,
        probe=probe,
        profiles=profiles or [],
        recursive=recursive,
    )

    bins, installs, bin_specs = scan_skills(ctx.skills_dir)

    findings: list[Finding] = []
    findings += check_bins(bins)
    findings += check_bin_versions(bin_specs)
    findings += check_install_arrays(installs)
    findings += check_fonts()
    findings += check_playwright_libs()

    if ctx.check_dir:
        if ctx.recursive:
            findings += check_projects_recursive(ctx.check_dir, probe=ctx.probe)
        else:
            findings += check_project_presets(ctx.check_dir, probe=ctx.probe)

    for prof in ctx.profiles:
        findings += check_profile(prof)

    if use_plugins:
        findings += run_plugins(ctx)

    return findings
