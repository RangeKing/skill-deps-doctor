from pathlib import Path
from unittest.mock import patch

import pytest

from skill_deps_doctor.hints import (
    HintDB,
    detect_linux_pkg_manager,
    extract_cmd,
    get_hint_db,
    init_hint_db,
    normalize_fix_command,
    os_family,
    reset_hint_db,
    which,
)


@pytest.fixture(autouse=True)
def _clean_singleton():
    """Reset the module-level HintDB between tests."""
    reset_hint_db()
    yield
    reset_hint_db()


class TestOsFamily:
    def test_returns_known_value(self):
        assert os_family() in {"linux", "macos", "windows", "other"}

    @patch("skill_deps_doctor.hints.sys")
    def test_linux(self, mock_sys):
        mock_sys.platform = "linux"
        assert os_family() == "linux"

    @patch("skill_deps_doctor.hints.sys")
    def test_darwin(self, mock_sys):
        mock_sys.platform = "darwin"
        assert os_family() == "macos"

    @patch("skill_deps_doctor.hints.sys")
    def test_win32(self, mock_sys):
        mock_sys.platform = "win32"
        assert os_family() == "windows"

    @patch("skill_deps_doctor.hints.sys")
    def test_freebsd(self, mock_sys):
        mock_sys.platform = "freebsd"
        assert os_family() == "other"


class TestWhich:
    def test_python_found(self):
        assert which("python") is not None or which("python3") is not None

    def test_nonexistent_binary(self):
        assert which("definitely_not_a_real_binary_xyz_123") is None


class TestHintDB:
    def test_loads_default_yaml(self):
        db = HintDB()
        assert db.fix_for_bin("node") is not None
        assert db.fix_for_bin("ffmpeg") is not None

    def test_alias_resolution(self):
        db = HintDB()
        node_fix = db.fix_for_bin("node")
        npm_fix = db.fix_for_bin("npm")
        assert node_fix == npm_fix

    def test_generic_fallback_for_unknown(self):
        db = HintDB()
        fix = db.fix_for_bin("some_obscure_tool_xyz")
        assert fix is not None
        assert "not in hint database" in fix

    @patch("skill_deps_doctor.hints.os_family", return_value="linux")
    def test_platform_specific_linux(self, _mock):
        db = HintDB()
        fix = db.fix_for_bin("git")
        assert fix is not None
        assert "install" in fix

    @patch("skill_deps_doctor.hints.os_family", return_value="macos")
    def test_platform_specific_macos(self, _mock):
        db = HintDB()
        fix = db.fix_for_bin("ffmpeg")
        assert fix is not None
        assert "brew" in fix

    @patch("skill_deps_doctor.hints.os_family", return_value="windows")
    def test_platform_specific_windows(self, _mock):
        db = HintDB()
        fix = db.fix_for_bin("node")
        assert fix is not None
        assert "choco" in fix

    def test_lib_hints(self):
        db = HintDB()
        assert "libnspr4.so" in db.lib_hints
        fix = db.fix_for_lib("libnspr4.so")
        assert fix is not None and "apt-get" in fix

    def test_font_hints(self):
        db = HintDB()
        assert "Noto Sans CJK" in db.font_hints
        patterns = db.fc_match_patterns("Noto Sans CJK")
        assert "NotoSansCJK" in patterns

    def test_profiles_loaded(self):
        db = HintDB()
        assert "slidev" in db.profiles
        assert "bins" in db.profiles["slidev"]

    def test_package_deps_loaded(self):
        db = HintDB()
        info = db.deps_for_npm_pkg("playwright")
        assert info is not None
        assert "note" in info

    def test_user_override(self, tmp_path):
        override = tmp_path / "custom.yaml"
        override.write_text(
            "bins:\n  my_custom_tool:\n    _all: 'pip install my-tool'\n",
            encoding="utf-8",
        )
        db = HintDB(override_path=override)
        fix = db.fix_for_bin("my_custom_tool")
        assert fix == "pip install my-tool"
        assert db.fix_for_bin("node") is not None


class TestSingleton:
    def test_get_creates_default(self):
        db = get_hint_db()
        assert isinstance(db, HintDB)

    def test_init_replaces(self):
        db1 = get_hint_db()
        db2 = init_hint_db()
        assert db1 is not db2
        assert get_hint_db() is db2


class TestExtractCmd:
    def test_sudo_command(self):
        assert extract_cmd("sudo apt-get install -y git") == "sudo apt-get install -y git"

    def test_brew_command(self):
        assert extract_cmd("brew install node") == "brew install node"

    def test_choco_command(self):
        assert extract_cmd("choco install nodejs-lts") == "choco install nodejs-lts"

    def test_install_description_returns_none(self):
        assert extract_cmd("Install Docker Desktop for Mac") is None

    def test_parenthetical_returns_none(self):
        assert extract_cmd("(built-in on macOS)") is None

    def test_unknown_prefix_returns_none(self):
        assert extract_cmd("Download from https://example.com") is None


class TestLinuxPkgManager:
    @patch("skill_deps_doctor.hints._linux_distro_tags", return_value={"fedora"})
    @patch("skill_deps_doctor.hints.which", side_effect=lambda n: "/usr/bin/" + n if n in {"apt-get", "dnf"} else None)
    @patch("skill_deps_doctor.hints.os_family", return_value="linux")
    def test_prefers_distro_match_over_other_installed(self, _mock_os, _mock_which, _mock_tags):
        assert detect_linux_pkg_manager() == "dnf"

    @patch("skill_deps_doctor.hints.which", side_effect=lambda n: "/usr/bin/dnf" if n == "dnf" else None)
    @patch("skill_deps_doctor.hints.os_family", return_value="linux")
    def test_detect_dnf(self, _mock_os, _mock_which):
        assert detect_linux_pkg_manager() == "dnf"

    @patch("skill_deps_doctor.hints.which", side_effect=lambda n: "/usr/bin/apk" if n == "apk" else None)
    @patch("skill_deps_doctor.hints.os_family", return_value="linux")
    def test_normalize_apk(self, _mock_os, _mock_which):
        cmd = normalize_fix_command("sudo apt-get install -y libpq-dev build-essential")
        assert cmd == "sudo apk add --no-cache libpq-dev build-essential"

    @patch("skill_deps_doctor.hints.which", side_effect=lambda n: "/usr/bin/pacman" if n == "pacman" else None)
    @patch("skill_deps_doctor.hints.os_family", return_value="linux")
    def test_normalize_pacman(self, _mock_os, _mock_which):
        cmd = normalize_fix_command("sudo apt-get install -y ffmpeg")
        assert cmd == "sudo pacman -S --needed --noconfirm ffmpeg"
