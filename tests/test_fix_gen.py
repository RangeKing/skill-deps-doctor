from unittest.mock import patch

from skill_deps_doctor.fix_gen import generate_fix_script
from skill_deps_doctor.models import Finding


class TestGenerateFixScript:
    @patch("skill_deps_doctor.fix_gen.os_family", return_value="linux")
    def test_bash_header(self, _mock):
        script = generate_fix_script([])
        assert script.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in script

    @patch("skill_deps_doctor.fix_gen.os_family", return_value="windows")
    def test_powershell_header(self, _mock):
        script = generate_fix_script([])
        assert "PowerShell" in script

    @patch("skill_deps_doctor.fix_gen.os_family", return_value="linux")
    def test_includes_runnable_commands(self, _mock):
        findings = [
            Finding(
                kind="missing_bin",
                item="git",
                detail="not found",
                fix="sudo apt-get install -y git",
            ),
        ]
        script = generate_fix_script(findings)
        assert "sudo apt-get install -y git" in script

    @patch("skill_deps_doctor.fix_gen.os_family", return_value="linux")
    def test_manual_steps_as_comments(self, _mock):
        findings = [
            Finding(
                kind="missing_bin",
                item="docker",
                detail="not found",
                fix="Install Docker Desktop for Mac",
            ),
        ]
        script = generate_fix_script(findings)
        assert "# (manual)" in script
        assert "Install Docker Desktop" in script

    @patch("skill_deps_doctor.fix_gen.os_family", return_value="linux")
    def test_skips_info_findings(self, _mock):
        findings = [
            Finding(kind="info_thing", item="ok", detail="all good", severity="info"),
            Finding(kind="missing_bin", item="git", detail="x", fix="sudo apt-get install -y git"),
        ]
        script = generate_fix_script(findings)
        assert "info_thing" not in script
        assert "sudo apt-get install -y git" in script

    @patch("skill_deps_doctor.fix_gen.os_family", return_value="linux")
    def test_no_fix_no_crash(self, _mock):
        findings = [
            Finding(kind="missing_bin", item="x", detail="x", fix=None),
        ]
        script = generate_fix_script(findings)
        assert "No automated fixes" in script

    @patch("skill_deps_doctor.fix_gen.os_family", return_value="windows")
    def test_linux_cmds_commented_on_windows(self, _mock):
        findings = [
            Finding(kind="missing_bin", item="git", detail="x", fix="sudo apt-get install -y git"),
        ]
        script = generate_fix_script(findings)
        assert "# Linux only:" in script
