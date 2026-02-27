import json
from pathlib import Path
from unittest.mock import patch

import pytest

from openclaw_skill_deps.checkers import (
    check_bins,
    check_fonts,
    check_install_arrays,
    check_package_deps,
    check_playwright_libs,
    check_project_presets,
    detect_playwright_runtime_need,
    scan_skills,
)
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


class TestScanSkills:
    def test_collects_bins(self, tmp_path):
        _make_skill(tmp_path, "skill-a", ["node", "ffmpeg"])
        _make_skill(tmp_path, "skill-b", ["pandoc", "node"])
        bins, installs, specs = scan_skills(tmp_path)
        assert set(bins) == {"node", "ffmpeg", "pandoc"}

    def test_empty_dir(self, tmp_path):
        bins, installs, specs = scan_skills(tmp_path)
        assert bins == []

    def test_version_specs_collected(self, tmp_path):
        _make_skill(tmp_path, "skill-a", ["node>=18", "ffmpeg"])
        bins, _, specs = scan_skills(tmp_path)
        assert "node" in bins
        assert "ffmpeg" in bins
        assert "node>=18" in specs
        assert "ffmpeg" in specs


class TestCheckBins:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_missing_bin(self, _mock_which):
        findings = check_bins(["nonexistent"])
        assert len(findings) == 1
        assert findings[0].kind == "missing_bin"
        assert findings[0].severity == "error"
        assert findings[0].fix is not None

    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/node")
    def test_present_bin(self, _mock_which):
        assert check_bins(["node"]) == []

    @patch("openclaw_skill_deps.checkers.which", side_effect=lambda n: "/usr/bin/a" if n == "a" else None)
    def test_partial(self, _mock_which):
        findings = check_bins(["a", "b"])
        assert len(findings) == 1
        assert findings[0].item == "b"


class TestCheckFonts:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_no_fc_list(self, _mock_which):
        findings = check_fonts()
        assert len(findings) == 1
        assert findings[0].item == "fc-list"
        assert findings[0].severity == "warn"

    @patch("openclaw_skill_deps.checkers.subprocess")
    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/fc-list")
    def test_missing_cjk(self, _mock_which, mock_sp):
        mock_sp.check_output.return_value = "DejaVu Sans\nLiberation Mono\n"
        findings = check_fonts()
        assert any(f.kind == "missing_font" for f in findings)

    @patch("openclaw_skill_deps.checkers.subprocess")
    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/fc-list")
    def test_cjk_present(self, _mock_which, mock_sp):
        mock_sp.check_output.return_value = "Noto Sans CJK SC\nDejaVu Sans\n"
        findings = check_fonts()
        font_missing = [f for f in findings if f.kind == "missing_font"]
        noto_missing = [f for f in font_missing if "Noto" in f.item]
        assert noto_missing == []

    @patch("openclaw_skill_deps.checkers.subprocess")
    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/fc-list")
    def test_probe_failure(self, _mock_which, mock_sp):
        mock_sp.check_output.side_effect = RuntimeError("fc-list failed")
        findings = check_fonts()
        assert len(findings) == 1
        assert findings[0].kind == "font_probe_failed"
        assert findings[0].severity == "warn"


class TestCheckInstallArrays:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_missing_install_bin(self, _mock_which, tmp_path):
        skill_path = tmp_path / "my-skill" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.touch()
        arr = [{"id": "dep1", "label": "Install Dep1", "bins": ["dep1-bin"]}]
        findings = check_install_arrays([(skill_path, arr)])
        assert len(findings) == 1
        assert findings[0].kind == "missing_install_bin"

    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/x")
    def test_all_present(self, _mock_which, tmp_path):
        skill_path = tmp_path / "my-skill" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.touch()
        arr = [{"id": "dep1", "bins": ["x"]}]
        assert check_install_arrays([(skill_path, arr)]) == []


class TestCheckPackageDeps:
    def test_known_npm_package(self):
        findings = check_package_deps(["playwright"], [])
        assert len(findings) >= 1
        assert findings[0].item == "npm:playwright"
        assert findings[0].severity == "warn"

    def test_known_pip_package(self):
        findings = check_package_deps([], ["opencv-python"])
        assert len(findings) >= 1
        assert findings[0].item == "pip:opencv-python"

    def test_unknown_packages_no_findings(self):
        findings = check_package_deps(["some-unknown-pkg"], ["another-unknown"])
        assert findings == []

    def test_mixed(self):
        findings = check_package_deps(["playwright", "express"], ["psycopg2", "requests"])
        items = {f.item for f in findings}
        assert "npm:playwright" in items
        assert "pip:psycopg2" in items
        assert "npm:express" not in items
        assert "pip:requests" not in items

    @patch("openclaw_skill_deps.hints.which", side_effect=lambda n: "/usr/bin/dnf" if n == "dnf" else None)
    @patch("openclaw_skill_deps.hints.os_family", return_value="linux")
    @patch("openclaw_skill_deps.checkers.os_family", return_value="linux")
    def test_linux_fix_normalized_for_dnf(self, _mock_os_checker, _mock_os_hints, _mock_which):
        findings = check_package_deps([], ["psycopg2"])
        assert len(findings) >= 1
        assert findings[0].fix is not None
        assert "dnf install -y libpq-dev" in findings[0].fix


class TestCheckProjectPresets:
    @patch("openclaw_skill_deps.checkers.which", return_value=None)
    def test_node_project_missing_bins(self, _mock_which, tmp_path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        findings = check_project_presets(tmp_path, probe=False)
        items = {f.item for f in findings if f.kind == "missing_bin"}
        assert "node" in items
        assert "npm" in items

    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/python3")
    def test_python_project_bins_ok(self, _mock_which, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        findings = check_project_presets(tmp_path, probe=False)
        missing = [f for f in findings if f.kind == "missing_bin"]
        assert missing == []

    def test_empty_dir(self, tmp_path):
        findings = check_project_presets(tmp_path, probe=False)
        assert all(f.kind != "missing_bin" for f in findings)

    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/node")
    def test_npm_package_deps_detected(self, _mock_which, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"playwright": "^1.0"}}),
            encoding="utf-8",
        )
        findings = check_project_presets(tmp_path, probe=False)
        pkg_hints = [f for f in findings if f.kind == "package_dep_hint"]
        assert any("playwright" in f.item for f in pkg_hints)

    @patch("openclaw_skill_deps.checkers.which", return_value="/usr/bin/python3")
    def test_pip_package_deps_detected(self, _mock_which, tmp_path):
        (tmp_path / "requirements.txt").write_text("opencv-python>=4.0\n", encoding="utf-8")
        findings = check_project_presets(tmp_path, probe=False)
        pkg_hints = [f for f in findings if f.kind == "package_dep_hint"]
        assert any("opencv-python" in f.item for f in pkg_hints)


class TestDetectPlaywrightRuntimeNeed:
    def test_skill_requires_playwright_bin(self, tmp_path):
        _make_skill(tmp_path, "web-skill", ["playwright>=1.40"])
        reasons = detect_playwright_runtime_need(skills_dir=tmp_path)
        assert any("skill:web-skill:requires-bin:playwright" == r for r in reasons)

    def test_project_npm_playwright(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"playwright": "^1.48.0"}}),
            encoding="utf-8",
        )
        reasons = detect_playwright_runtime_need(check_dir=tmp_path)
        assert "project:npm:playwright" in reasons

    def test_profile_with_playwright_libs(self):
        reasons = detect_playwright_runtime_need(profiles=["web-scraping"])
        assert "profile:web-scraping:core-playwright-libs" in reasons


class TestCheckPlaywrightLibs:
    def test_disabled_returns_empty(self):
        assert check_playwright_libs(enabled=False) == []

    @patch("openclaw_skill_deps.checkers.os_family", return_value="linux")
    @patch("openclaw_skill_deps.checkers.subprocess")
    @patch("openclaw_skill_deps.checkers.which", return_value="/sbin/ldconfig")
    def test_enabled_reports_missing_libs(self, _mock_which, mock_sp, _mock_os):
        mock_sp.check_output.return_value = ""
        findings = check_playwright_libs(enabled=True, reason="project:npm:playwright")
        assert len(findings) > 0
        assert findings[0].kind == "missing_lib"
        assert findings[0].code == "PLAYWRIGHT_LIB_MISSING"
