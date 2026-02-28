from skill_deps_doctor.migration import migrate_hints_to_v1, migration_needed


class TestMigrateHintsToV1:
    def test_adds_schema_version_and_sections(self):
        src = {"bins": {"node": {"linux": "x"}}}
        migrated, changes = migrate_hints_to_v1(src)
        assert migrated["schema_version"] == 1
        assert "libs" in migrated and isinstance(migrated["libs"], dict)
        assert "package_deps" in migrated and isinstance(migrated["package_deps"], dict)
        assert len(changes) > 0

    def test_normalizes_package_deps_shape(self):
        src = {
            "schema_version": 1,
            "bins": {},
            "libs": {},
            "fonts": {},
            "profiles": {},
            "package_deps": {"npm": [], "pip": {}},
            "version_commands": {},
            "transitive_deps": {},
        }
        migrated, changes = migrate_hints_to_v1(src)
        assert isinstance(migrated["package_deps"]["npm"], dict)
        assert any("package_deps.npm" in c for c in changes)

    def test_migration_needed_false_for_clean_data(self):
        src = {
            "schema_version": 1,
            "bins": {},
            "libs": {},
            "fonts": {},
            "profiles": {},
            "package_deps": {"npm": {}, "pip": {}},
            "version_commands": {},
            "transitive_deps": {},
        }
        assert migration_needed(src) is False
