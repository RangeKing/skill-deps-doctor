from pathlib import Path

from skill_deps_doctor.models import CheckContext, Finding


class TestFinding:
    def test_defaults(self):
        f = Finding(kind="missing_bin", item="node", detail="not found")
        assert f.severity == "error"
        assert f.fix is None
        assert f.code is None
        assert f.evidence is None
        assert f.confidence is None

    def test_custom_severity(self):
        f = Finding(kind="info", item="x", detail="ok", severity="info")
        assert f.severity == "info"

    def test_with_fix(self):
        f = Finding(kind="missing_bin", item="git", detail="nope", fix="apt install git")
        assert f.fix == "apt install git"

    def test_as_dict(self):
        f = Finding(kind="k", item="i", detail="d", fix="f", severity="warn")
        d = f.__dict__
        assert d == {
            "kind": "k",
            "item": "i",
            "detail": "d",
            "fix": "f",
            "severity": "warn",
            "code": None,
            "evidence": None,
            "confidence": None,
        }


class TestCheckContext:
    def test_defaults(self):
        ctx = CheckContext(skills_dir=Path("/tmp/skills"))
        assert ctx.check_dir is None
        assert ctx.probe is False
        assert ctx.profiles == []
        assert ctx.recursive is False
        assert ctx.plugin_api_version == 1

    def test_full(self):
        ctx = CheckContext(
            skills_dir=Path("/skills"),
            check_dir=Path("/project"),
            probe=True,
            profiles=["slidev"],
            recursive=True,
            plugin_api_version=2,
        )
        assert ctx.check_dir == Path("/project")
        assert ctx.profiles == ["slidev"]
        assert ctx.recursive is True
        assert ctx.plugin_api_version == 2
