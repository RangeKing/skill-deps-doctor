from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .hints import os_family
from .models import Finding

SCHEMA_VERSION = 1


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finding_signature(data: dict[str, object]) -> tuple[str, str, str, str]:
    kind = str(data.get("kind", ""))
    item = str(data.get("item", ""))
    severity = str(data.get("severity", ""))
    code = str(data.get("code") or "")
    return (kind, item, severity, code)


def findings_to_dicts(findings: list[Finding]) -> list[dict[str, object]]:
    return [asdict(f) for f in findings]


def build_snapshot(
    findings: list[Finding],
    *,
    skills_dir: Path,
    check_dir: Path | None,
    profiles: list[str],
    probe: bool,
    recursive: bool,
    no_plugins: bool,
    hints_file: Path | None,
    baseline_path: Path | None = None,
    new_since_baseline: list[Finding] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": _now_utc(),
        "tool": {
            "name": "openclaw-skill-deps",
        },
        "environment": {
            "os_family": os_family(),
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
        },
        "inputs": {
            "skills_dir": str(skills_dir),
            "check_dir": str(check_dir) if check_dir else None,
            "profiles": profiles,
            "probe": probe,
            "recursive": recursive,
            "no_plugins": no_plugins,
            "hints_file": str(hints_file) if hints_file else None,
        },
        "findings": findings_to_dicts(findings),
    }

    if baseline_path:
        baseline_obj: dict[str, object] = {"path": str(baseline_path)}
        if new_since_baseline is not None:
            baseline_obj["new_findings_count"] = len(new_since_baseline)
            baseline_obj["new_findings"] = findings_to_dicts(new_since_baseline)
        payload["baseline"] = baseline_obj

    return payload


def write_snapshot(path: Path, snapshot: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def load_baseline_findings(path: Path) -> list[dict[str, object]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to read baseline JSON: {e}") from e

    if isinstance(data, dict):
        findings = data.get("findings")
        if isinstance(findings, list):
            if all(isinstance(x, dict) for x in findings):
                return list(findings)
            raise ValueError("Baseline snapshot 'findings' must be an array of objects")
        raise ValueError("Baseline JSON object must contain 'findings' array")

    if isinstance(data, list):
        if all(isinstance(x, dict) for x in data):
            return list(data)
        raise ValueError("Baseline JSON array must contain objects")

    raise ValueError("Baseline JSON must be either an object or an array")


def find_new_findings(
    current: list[Finding],
    baseline_entries: list[dict[str, object]],
) -> list[Finding]:
    baseline_set = {_finding_signature(x) for x in baseline_entries}

    new_items: list[Finding] = []
    for finding in current:
        if finding.severity not in {"error", "warn"}:
            continue
        signature = _finding_signature(asdict(finding))
        if signature not in baseline_set:
            new_items.append(finding)

    return new_items
