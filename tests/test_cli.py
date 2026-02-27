import json
from pathlib import Path
from unittest.mock import patch

import pytest

from openclaw_skill_deps.cli import main
from openclaw_skill_deps.hints import reset_hint_db


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


class TestMainExitCodes:
    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/x")
    @patch("openclaw_skill_deps.checkers.subprocess")
    def test_pass_returns_0(self, _mock_sp, _mock_which, tmp_path, capsys):
        _mock_sp.check_output.return_value = "Noto Sans CJK SC\nWenQuanYi Zen Hei"
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "test-skill", ["x"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills)]):
            rc = main()

        assert rc == 0
        assert "PASS" in capsys.readouterr().out

    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_fail_returns_2(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "test-skill", ["nonexistent"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills)]):
            rc = main()

        assert rc == 2
        assert "FAIL" in capsys.readouterr().out


class TestJsonOutput:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_json_has_severity(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["missing_tool"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--json"]):
            rc = main()

        data = json.loads(capsys.readouterr().out)
        assert len(data) > 0
        assert all("severity" in item for item in data)
        assert rc == 2


class TestInfoOnlyNoFail:
    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/fc-list")
    @patch("openclaw_skill_deps.checkers.subprocess")
    def test_info_findings_exit_0(self, mock_sp, _mock_which, tmp_path, capsys):
        mock_sp.check_output.return_value = "Noto Sans CJK SC\nWenQuanYi"
        skills = tmp_path / "skills"
        skills.mkdir()

        with patch("sys.argv", ["prog", "--skills-dir", str(skills)]):
            rc = main()

        assert rc == 0


class TestVerboseQuiet:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_quiet_shows_only_errors(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["missing_tool"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "-q"]):
            main()

        out = capsys.readouterr().out
        assert "[ERR]" in out
        assert "[WARN]" not in out

    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_verbose_shows_os(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["missing_tool"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "-v"]):
            main()

        out = capsys.readouterr().out
        assert "OS:" in out


class TestListProfiles:
    def test_list_profiles(self, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--list-profiles"]):
            rc = main()

        assert rc == 0
        out = capsys.readouterr().out
        assert "slidev" in out


class TestFixMode:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_fix_outputs_script(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["git"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--fix"]):
            rc = main()

        out = capsys.readouterr().out
        assert "Fix script" in out or "#!/usr/bin/env bash" in out or "PowerShell" in out


class TestProfileFlag:
    @patch("openclaw_skill_deps.profiles.which", return_value=None)
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_profile_findings_included(self, _mock_which1, _mock_which2, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--profile", "whisper", "--json"]):
            main()

        data = json.loads(capsys.readouterr().out)
        items = {d["item"] for d in data}
        assert "ffmpeg" in items or "python3" in items


class TestHintsFile:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_custom_hints(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["my_custom_bin"])

        hints = tmp_path / "custom.yaml"
        hints.write_text(
            "bins:\n  my_custom_bin:\n    _all: 'pip install my-custom-bin'\n",
            encoding="utf-8",
        )

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--hints-file", str(hints), "--json"]):
            main()

        data = json.loads(capsys.readouterr().out)
        custom = [d for d in data if d["item"] == "my_custom_bin"]
        assert len(custom) >= 1
        assert custom[0]["fix"] == "pip install my-custom-bin"


class TestRecursiveFlag:
    @patch("openclaw_skill_deps.checkers.subprocess")
    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/node")
    def test_recursive_finds_subprojects(self, _mock_which, mock_sp, tmp_path, capsys):
        mock_sp.check_output.return_value = "Noto Sans CJK SC\nWenQuanYi Zen Hei"
        skills = tmp_path / "skills"
        skills.mkdir()
        root = tmp_path / "mono"
        root.mkdir()
        sub = root / "packages" / "app"
        sub.mkdir(parents=True)
        (sub / "package.json").write_text(
            '{"dependencies":{"playwright":"^1"}}', encoding="utf-8",
        )

        with patch("sys.argv", [
            "prog", "--skills-dir", str(skills),
            "--check-dir", str(root), "--recursive", "--json",
        ]):
            main()

        data = json.loads(capsys.readouterr().out)
        pkg_hints = [d for d in data if d["kind"] == "package_dep_hint"]
        assert any("playwright" in d["item"] for d in pkg_hints)


class TestNoPlugins:
    def test_no_plugins_flag_accepted(self, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--no-plugins", "-q"]):
            rc = main()

        assert rc == 0


class TestGraphFlag:
    @patch("openclaw_skill_deps.graph.probe_bin_version", return_value="20.11.1")
    @patch("openclaw_skill_deps.graph.which", return_value="/usr/bin/node")
    def test_tree_output(self, _wh, _probe, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "demo", ["node>=18"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--graph", "tree"]):
            rc = main()

        assert rc == 0
        out = capsys.readouterr().out
        assert "demo" in out
        assert "node" in out

    @patch("openclaw_skill_deps.graph.probe_bin_version", return_value="20.11.1")
    @patch("openclaw_skill_deps.graph.which", return_value="/usr/bin/node")
    def test_dot_output(self, _wh, _probe, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "demo", ["node"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--graph", "dot"]):
            rc = main()

        assert rc == 0
        out = capsys.readouterr().out
        assert "digraph deps" in out


class TestPlatformMatrix:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_matrix_output(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["node", "ffmpeg"])

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--platform-matrix"]):
            rc = main()

        assert rc == 2
        out = capsys.readouterr().out
        assert "Linux" in out
        assert "macOS" in out
        assert "Windows" in out
        assert "node" in out


class TestSnapshotAndBaseline:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_snapshot_file_written(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "s", ["missing_tool"])
        snapshot = tmp_path / "reports" / "snapshot.json"

        with patch("sys.argv", [
            "prog", "--skills-dir", str(skills), "--json", "--snapshot", str(snapshot),
        ]):
            rc = main()

        assert rc == 2
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        assert "schema_version" in payload
        assert "findings" in payload
        _ = capsys.readouterr()

    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_fail_on_new_uses_exit_3(self, _mock_which, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()

        baseline = tmp_path / "baseline.json"
        baseline.write_text("[]", encoding="utf-8")

        with patch("sys.argv", [
            "prog", "--skills-dir", str(skills),
            "--baseline", str(baseline), "--fail-on-new", "-q",
        ]):
            rc = main()

        assert rc == 3
        _ = capsys.readouterr()

    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/fc-list")
    @patch("openclaw_skill_deps.checkers.subprocess")
    def test_invalid_baseline_becomes_error(self, mock_sp, _mock_which, tmp_path, capsys):
        mock_sp.check_output.return_value = "Noto Sans CJK SC\nWenQuanYi Zen Hei"
        skills = tmp_path / "skills"
        skills.mkdir()

        baseline = tmp_path / "baseline.json"
        baseline.write_text('{"foo":1}', encoding="utf-8")

        with patch("sys.argv", [
            "prog", "--skills-dir", str(skills), "--baseline", str(baseline), "--json",
        ]):
            rc = main()

        assert rc == 2
        data = json.loads(capsys.readouterr().out)
        assert any(d["kind"] == "baseline_invalid" for d in data)


class TestValidateHintsFlag:
    def test_validate_hints_ok(self, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()

        with patch("sys.argv", ["prog", "--skills-dir", str(skills), "--validate-hints"]):
            rc = main()

        assert rc == 0
        out = capsys.readouterr().out
        assert "HINTS OK" in out

    def test_validate_hints_invalid(self, tmp_path, capsys):
        skills = tmp_path / "skills"
        skills.mkdir()
        hints = tmp_path / "bad-hints.yaml"
        hints.write_text("schema_version: 999\nbins: {}\n", encoding="utf-8")

        with patch("sys.argv", [
            "prog",
            "--skills-dir", str(skills),
            "--hints-file", str(hints),
            "--validate-hints",
        ]):
            rc = main()

        assert rc == 2
        out = capsys.readouterr().out
        assert "HINTS INVALID" in out
