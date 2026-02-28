from pathlib import Path
from unittest.mock import patch

import pytest

from skill_deps_doctor import run_check
from skill_deps_doctor.hints import reset_hint_db


@pytest.fixture(autouse=True)
def _clean():
    reset_hint_db()
    yield
    reset_hint_db()


def _make_skill(skills_dir: Path, name: str, bins: list[str]) -> None:
    d = skills_dir / name
    d.mkdir(parents=True, exist_ok=True)
    bins_yaml = "\n".join(f"        - {b}" for b in bins)
    (d / "SKILL.md").write_text(
        f"""\
---
name: {name}
metadata:
  clawdbot:
    requires:
      bins:
{bins_yaml}
---
# {name}
""",
        encoding="utf-8",
    )


class TestRunCheck:
    @patch("skill_deps_doctor.versions.which", return_value="/usr/bin/x")
    @patch("skill_deps_doctor.checkers.which", return_value="/usr/bin/x")
    @patch("skill_deps_doctor.checkers.subprocess")
    def test_all_pass(self, mock_sp, _mock_which, _mock_ver_which, tmp_path):
        mock_sp.check_output.return_value = "Noto Sans CJK SC\nWenQuanYi Zen Hei"
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["x"])

        findings = run_check(skills, use_plugins=False)
        errors = [f for f in findings if f.severity == "error"]
        assert errors == []

    @patch("skill_deps_doctor.versions.which", return_value=None)
    @patch("skill_deps_doctor.checkers.which", return_value=None)
    def test_missing_bins_detected(self, _mock_which, _mock_ver_which, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["missing_tool"])

        findings = run_check(skills, use_plugins=False)
        errors = [f for f in findings if f.severity == "error"]
        assert any(f.item == "missing_tool" for f in errors)

    @patch("skill_deps_doctor.profiles.which", return_value=None)
    @patch("skill_deps_doctor.checkers.which", return_value=None)
    def test_with_profile(self, _mock1, _mock2, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()

        findings = run_check(skills, profiles=["whisper"], use_plugins=False)
        items = {f.item for f in findings if f.kind == "missing_bin"}
        assert "ffmpeg" in items or "python3" in items

    def test_returns_list(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        result = run_check(skills, use_plugins=False)
        assert isinstance(result, list)

    @patch("skill_deps_doctor.checkers.subprocess")
    @patch("skill_deps_doctor.checkers.which", return_value="/usr/bin/node")
    def test_check_dir(self, _mock_which, mock_sp, tmp_path):
        mock_sp.check_output.return_value = "Noto Sans CJK SC\nWenQuanYi Zen Hei"
        skills = tmp_path / "skills"
        skills.mkdir()
        proj = tmp_path / "project"
        proj.mkdir()
        (proj / "package.json").write_text('{"dependencies":{"playwright":"^1"}}', encoding="utf-8")

        findings = run_check(skills, check_dir=proj, use_plugins=False)
        pkg_hints = [f for f in findings if f.kind == "package_dep_hint"]
        assert any("playwright" in f.item for f in pkg_hints)

    @patch("skill_deps_doctor.checkers.subprocess")
    @patch("skill_deps_doctor.checkers.which", return_value="/usr/bin/node")
    def test_recursive(self, _mock_which, mock_sp, tmp_path):
        mock_sp.check_output.return_value = "Noto Sans CJK SC\nWenQuanYi Zen Hei"
        skills = tmp_path / "skills"
        skills.mkdir()

        root = tmp_path / "mono"
        root.mkdir()
        sub = root / "packages" / "frontend"
        sub.mkdir(parents=True)
        (sub / "package.json").write_text('{"dependencies":{"playwright":"^1"}}', encoding="utf-8")

        findings = run_check(skills, check_dir=root, recursive=True, use_plugins=False)
        pkg_hints = [f for f in findings if f.kind == "package_dep_hint"]
        assert any("playwright" in f.item for f in pkg_hints)
