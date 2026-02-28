from unittest.mock import patch

import pytest

from skill_deps_doctor.hints import reset_hint_db
from skill_deps_doctor.profiles import check_profile, list_profiles


@pytest.fixture(autouse=True)
def _clean():
    reset_hint_db()
    yield
    reset_hint_db()


class TestListProfiles:
    def test_returns_nonempty(self):
        profiles = list_profiles()
        assert len(profiles) > 0
        names = [n for n, _ in profiles]
        assert "slidev" in names

    def test_each_has_description(self):
        for name, desc in list_profiles():
            assert isinstance(name, str)
            assert isinstance(desc, str)


class TestCheckProfile:
    def test_unknown_profile(self):
        findings = check_profile("nonexistent_profile_xyz")
        assert len(findings) == 1
        assert findings[0].kind == "unknown_profile"
        assert "Available" in findings[0].detail

    @patch("skill_deps_doctor.profiles.which", return_value=None)
    def test_missing_bins(self, _mock_which):
        findings = check_profile("slidev")
        missing = [f for f in findings if f.kind == "missing_bin"]
        items = {f.item for f in missing}
        assert "node" in items
        assert "npm" in items

    @patch("skill_deps_doctor.profiles.which", return_value="/usr/bin/node")
    def test_bins_present(self, _mock_which):
        findings = check_profile("slidev")
        missing = [f for f in findings if f.kind == "missing_bin"]
        assert missing == []

    def test_profile_font_findings(self):
        findings = check_profile("slidev")
        font_findings = [f for f in findings if f.kind == "profile_requires_font"]
        assert len(font_findings) > 0
        assert font_findings[0].severity == "warn"

    @patch("skill_deps_doctor.profiles.which", return_value=None)
    def test_whisper_profile(self, _mock_which):
        findings = check_profile("whisper")
        items = {f.item for f in findings if f.kind == "missing_bin"}
        assert "python3" in items
        assert "ffmpeg" in items
