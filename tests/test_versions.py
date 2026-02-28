from unittest.mock import patch

import pytest

from skill_deps_doctor.hints import reset_hint_db
from skill_deps_doctor.versions import (
    VersionReq,
    check_bin_versions,
    compare_versions,
    parse_bin_spec,
    probe_bin_version,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_hint_db()
    yield
    reset_hint_db()


class TestParseBinSpec:
    def test_plain_name(self):
        vr = parse_bin_spec("node")
        assert vr.name == "node"
        assert vr.operator is None
        assert vr.version is None
        assert not vr.has_constraint

    def test_gte(self):
        vr = parse_bin_spec("node>=18")
        assert vr == VersionReq(name="node", operator=">=", version="18")
        assert vr.has_constraint

    def test_eq(self):
        vr = parse_bin_spec("python3==3.10.12")
        assert vr.name == "python3"
        assert vr.operator == "=="
        assert vr.version == "3.10.12"

    def test_lt(self):
        vr = parse_bin_spec("npm<10")
        assert vr.operator == "<"

    def test_ne(self):
        vr = parse_bin_spec("git!=2.30.0")
        assert vr.operator == "!="

    def test_whitespace(self):
        vr = parse_bin_spec("  node >= 18 ")
        assert vr.name == "node"
        assert vr.operator == ">="
        assert vr.version == "18"


class TestCompareVersions:
    def test_gte_pass(self):
        assert compare_versions("20.11.1", ">=", "18") is True

    def test_gte_fail(self):
        assert compare_versions("16.3.0", ">=", "18") is False

    def test_eq(self):
        assert compare_versions("3.10.12", "==", "3.10.12") is True
        assert compare_versions("3.10.11", "==", "3.10.12") is False

    def test_lt(self):
        assert compare_versions("9.8.0", "<", "10") is True
        assert compare_versions("10.0.0", "<", "10") is False

    def test_gt(self):
        assert compare_versions("18.1.0", ">", "18.0.0") is True
        assert compare_versions("18.0.0", ">", "18.0.0") is False

    def test_lte(self):
        assert compare_versions("18.0.0", "<=", "18.0.0") is True
        assert compare_versions("18.0.1", "<=", "18.0.0") is False

    def test_ne(self):
        assert compare_versions("3.10.0", "!=", "3.10.1") is True
        assert compare_versions("3.10.1", "!=", "3.10.1") is False

    def test_padding(self):
        assert compare_versions("20", ">=", "18.0.0") is True
        assert compare_versions("18.0.0", ">=", "18") is True


class TestProbeBinVersion:
    @patch("skill_deps_doctor.versions.which", return_value="/usr/bin/node")
    @patch("skill_deps_doctor.versions.subprocess")
    def test_with_version_command(self, mock_sp, _wh):
        mock_sp.check_output.return_value = "v20.11.1\n"
        mock_sp.STDOUT = -2
        v = probe_bin_version("node")
        assert v == "20.11.1"

    @patch("skill_deps_doctor.versions.which", return_value="/usr/bin/unknown_tool")
    @patch("skill_deps_doctor.versions.subprocess")
    def test_generic_fallback(self, mock_sp, _wh):
        mock_sp.check_output.return_value = "unknown_tool version 1.2.3"
        mock_sp.STDOUT = -2
        v = probe_bin_version("unknown_tool")
        assert v == "1.2.3"


class TestCheckBinVersions:
    @patch("skill_deps_doctor.versions.probe_bin_version", return_value="20.11.1")
    @patch("skill_deps_doctor.versions.which", return_value="/usr/bin/node")
    def test_version_ok(self, _wh, _probe):
        findings = check_bin_versions(["node>=18"])
        assert len(findings) == 1
        assert findings[0].kind == "version_ok"
        assert findings[0].severity == "info"

    @patch("skill_deps_doctor.versions.probe_bin_version", return_value="16.3.0")
    @patch("skill_deps_doctor.versions.which", return_value="/usr/bin/node")
    def test_version_mismatch(self, _wh, _probe):
        findings = check_bin_versions(["node>=18"])
        assert len(findings) == 1
        assert findings[0].kind == "version_mismatch"
        assert findings[0].severity == "error"

    @patch("skill_deps_doctor.versions.which", return_value=None)
    def test_missing_bin_skipped(self, _wh):
        findings = check_bin_versions(["node>=18"])
        assert findings == []

    def test_no_constraint_skipped(self):
        findings = check_bin_versions(["node"])
        assert findings == []

    @patch("skill_deps_doctor.versions.probe_bin_version", return_value=None)
    @patch("skill_deps_doctor.versions.which", return_value="/usr/bin/node")
    def test_version_unknown(self, _wh, _probe):
        findings = check_bin_versions(["node>=18"])
        assert len(findings) == 1
        assert findings[0].kind == "version_unknown"
        assert findings[0].severity == "warn"
