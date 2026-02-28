from skill_deps_doctor.schemas import HINTS_SCHEMA_VERSION, validate_hints_data


class TestValidateHintsData:
    def test_accepts_minimal_valid_shape(self):
        data = {
            "schema_version": HINTS_SCHEMA_VERSION,
            "bins": {},
            "libs": {},
            "fonts": {},
            "profiles": {},
            "package_deps": {"npm": {}, "pip": {}},
            "version_commands": {},
            "transitive_deps": {},
        }
        assert validate_hints_data(data) == []

    def test_missing_schema_version(self):
        errs = validate_hints_data({"bins": {}})
        assert any("schema_version" in e for e in errs)

    def test_rejects_wrong_types(self):
        errs = validate_hints_data({
            "schema_version": HINTS_SCHEMA_VERSION,
            "bins": [],
            "package_deps": {"npm": []},
        })
        assert any("Top-level 'bins' must be a mapping" in e for e in errs)
        assert any("'package_deps.npm' must be a mapping" in e for e in errs)
