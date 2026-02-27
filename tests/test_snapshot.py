import json
from pathlib import Path

from openclaw_skill_deps.models import Finding
from openclaw_skill_deps.snapshot import (
    build_snapshot,
    find_new_findings,
    load_baseline_findings,
    write_snapshot,
)


class TestLoadBaselineFindings:
    def test_accepts_findings_array(self, tmp_path):
        p = tmp_path / "baseline.json"
        p.write_text(json.dumps([{"kind": "k", "item": "i", "severity": "warn"}]), encoding="utf-8")
        out = load_baseline_findings(p)
        assert len(out) == 1
        assert out[0]["kind"] == "k"

    def test_accepts_snapshot_object(self, tmp_path):
        p = tmp_path / "snapshot.json"
        p.write_text(
            json.dumps({"schema_version": 1, "findings": [{"kind": "k", "item": "i", "severity": "error"}]}),
            encoding="utf-8",
        )
        out = load_baseline_findings(p)
        assert len(out) == 1
        assert out[0]["severity"] == "error"

    def test_rejects_invalid_shape(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"foo": 1}), encoding="utf-8")
        try:
            load_baseline_findings(p)
        except ValueError as e:
            assert "must contain 'findings'" in str(e)
        else:
            raise AssertionError("expected ValueError")


class TestFindNewFindings:
    def test_only_new_warn_error(self):
        current = [
            Finding(kind="missing_bin", item="node", detail="x", severity="error", code="MISSING_BIN"),
            Finding(kind="missing_font", item="Noto Sans CJK", detail="y", severity="warn"),
            Finding(kind="version_ok", item="node", detail="ok", severity="info"),
        ]
        baseline = [
            {"kind": "missing_bin", "item": "node", "severity": "error", "code": "MISSING_BIN"},
        ]
        new_items = find_new_findings(current, baseline)
        assert len(new_items) == 1
        assert new_items[0].kind == "missing_font"


class TestBuildAndWriteSnapshot:
    def test_build_and_write(self, tmp_path):
        findings = [Finding(kind="missing_bin", item="git", detail="missing", severity="error")]
        snapshot = build_snapshot(
            findings,
            skills_dir=Path("/tmp/skills"),
            check_dir=None,
            profiles=["whisper"],
            probe=True,
            recursive=False,
            no_plugins=False,
            hints_file=None,
            baseline_path=Path("/tmp/base.json"),
            new_since_baseline=findings,
        )
        assert snapshot["schema_version"] == 1
        assert "environment" in snapshot
        assert "findings" in snapshot

        out = tmp_path / "reports" / "snapshot.json"
        write_snapshot(out, snapshot)
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["inputs"]["profiles"] == ["whisper"]
        assert loaded["baseline"]["new_findings_count"] == 1
