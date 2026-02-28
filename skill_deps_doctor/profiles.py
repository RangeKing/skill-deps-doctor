from __future__ import annotations

from .hints import get_hint_db, which
from .models import Finding


def list_profiles() -> list[tuple[str, str]]:
    """Return ``[(name, description), ...]`` for every registered profile."""
    db = get_hint_db()
    return [
        (name, prof.get("description", ""))
        for name, prof in sorted(db.profiles.items())
    ]


def check_profile(profile_name: str) -> list[Finding]:
    """Run dependency checks for a named profile."""
    db = get_hint_db()
    profile = db.profiles.get(profile_name)

    if profile is None:
        available = ", ".join(sorted(db.profiles))
        return [
            Finding(
                kind="unknown_profile",
                item=profile_name,
                detail=f"Unknown profile '{profile_name}'. Available: {available}",
                severity="warn",
            )
        ]

    findings: list[Finding] = []
    desc = profile.get("description", profile_name)

    for b in profile.get("bins", []):
        if which(b) is None:
            findings.append(
                Finding(
                    kind="missing_bin",
                    item=b,
                    detail=f"Profile '{profile_name}' ({desc}) requires '{b}'",
                    fix=db.fix_for_bin(b),
                )
            )

    for font in profile.get("fonts", []):
        fix = db.fix_for_font(font)
        findings.append(
            Finding(
                kind="profile_requires_font",
                item=font,
                detail=f"Profile '{profile_name}' recommends font '{font}'",
                fix=fix,
                severity="warn",
            )
        )

    for lib in profile.get("libs", []):
        fix = db.fix_for_lib(lib)
        findings.append(
            Finding(
                kind="profile_requires_lib",
                item=lib,
                detail=f"Profile '{profile_name}' recommends lib '{lib}'",
                fix=fix,
                severity="warn",
            )
        )

    return findings
