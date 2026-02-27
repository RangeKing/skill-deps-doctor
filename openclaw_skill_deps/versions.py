from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from .hints import get_hint_db, which
from .models import Finding

_VERSION_RE = re.compile(r"^([a-zA-Z0-9_.+\-]+?)\s*(>=|<=|==|!=|>|<)\s*(.+)$")
_GENERIC_VERSION_RE = re.compile(r"(\d+(?:\.\d+)+)")


@dataclass
class VersionReq:
    name: str
    operator: str | None = None
    version: str | None = None

    @property
    def has_constraint(self) -> bool:
        return self.operator is not None and self.version is not None


def parse_bin_spec(spec: str) -> VersionReq:
    """Parse ``'node>=18'`` into ``VersionReq(name='node', operator='>=', version='18')``."""
    spec = spec.strip()
    m = _VERSION_RE.match(spec)
    if m:
        return VersionReq(name=m.group(1), operator=m.group(2), version=m.group(3))
    return VersionReq(name=spec)


def _normalise(v: str) -> list[int]:
    parts: list[int] = []
    for segment in v.split("."):
        digits = re.match(r"\d+", segment)
        parts.append(int(digits.group()) if digits else 0)
    return parts


def compare_versions(actual: str, operator: str, required: str) -> bool:
    """Compare *actual* against *required* using *operator*."""
    a = _normalise(actual)
    r = _normalise(required)
    max_len = max(len(a), len(r))
    a.extend([0] * (max_len - len(a)))
    r.extend([0] * (max_len - len(r)))

    if operator == ">=":
        return a >= r
    if operator == "<=":
        return a <= r
    if operator == "==":
        return a == r
    if operator == "!=":
        return a != r
    if operator == ">":
        return a > r
    if operator == "<":
        return a < r
    return True


def probe_bin_version(bin_name: str) -> str | None:
    """Run a binary's version command and extract the version string."""
    db = get_hint_db()
    info = db.version_command(bin_name)

    if info is None:
        return _generic_probe(bin_name)

    cmd = info["cmd"]
    pattern = info.get("pattern")

    try:
        out = subprocess.check_output(
            cmd, shell=True, text=True, errors="ignore",
            stderr=subprocess.STDOUT, timeout=10,
        ).strip()
    except Exception:
        return None

    if pattern:
        m = re.search(pattern, out)
        return m.group(1) if m else None

    m = _GENERIC_VERSION_RE.search(out)
    return m.group(1) if m else None


def _generic_probe(bin_name: str) -> str | None:
    """Fallback: try ``<bin> --version`` and extract digits."""
    path = which(bin_name)
    if path is None:
        return None
    try:
        out = subprocess.check_output(
            [path, "--version"], text=True, errors="ignore",
            stderr=subprocess.STDOUT, timeout=10,
        ).strip()
    except Exception:
        return None
    m = _GENERIC_VERSION_RE.search(out)
    return m.group(1) if m else None


def check_bin_versions(bin_specs: list[str]) -> list[Finding]:
    """Check version constraints for binaries that are present."""
    findings: list[Finding] = []
    for spec in bin_specs:
        vr = parse_bin_spec(spec)
        if not vr.has_constraint:
            continue
        if which(vr.name) is None:
            continue

        actual = probe_bin_version(vr.name)
        if actual is None:
            findings.append(Finding(
                kind="version_unknown",
                item=vr.name,
                detail=f"'{vr.name}' found but unable to determine version (need {vr.operator}{vr.version})",
                severity="warn",
            ))
            continue

        assert vr.operator is not None and vr.version is not None
        if not compare_versions(actual, vr.operator, vr.version):
            findings.append(Finding(
                kind="version_mismatch",
                item=vr.name,
                detail=f"'{vr.name}' version {actual} does not satisfy {vr.operator}{vr.version}",
                severity="error",
            ))
        else:
            findings.append(Finding(
                kind="version_ok",
                item=vr.name,
                detail=f"'{vr.name}' version {actual} satisfies {vr.operator}{vr.version}",
                severity="info",
            ))

    return findings
