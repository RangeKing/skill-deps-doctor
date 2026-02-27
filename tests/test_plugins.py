from pathlib import Path
from unittest.mock import patch

import pytest

from openclaw_skill_deps.hints import reset_hint_db
from openclaw_skill_deps.models import CheckContext, Finding
from openclaw_skill_deps.plugins import load_plugins, run_plugins


@pytest.fixture(autouse=True)
def _clean():
    reset_hint_db()
    yield
    reset_hint_db()


def _make_ctx(tmp_path: Path) -> CheckContext:
    return CheckContext(skills_dir=tmp_path, check_dir=None, probe=False)


class TestLoadPlugins:
    def test_returns_list(self):
        plugins = load_plugins()
        assert isinstance(plugins, list)

    def test_no_builtin_plugins(self):
        plugins = load_plugins()
        assert plugins == []


class TestRunPlugins:
    def test_empty_plugin_list(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        findings = run_plugins(ctx, plugins=[])
        assert findings == []

    def test_plugin_findings_tagged(self, tmp_path):
        def my_plugin(ctx: CheckContext) -> list[Finding]:
            return [
                Finding(kind="gpu_missing", item="cuda", detail="CUDA not found", severity="error"),
            ]

        ctx = _make_ctx(tmp_path)
        findings = run_plugins(ctx, plugins=[("my_gpu", my_plugin)])
        assert len(findings) == 1
        assert "[plugin:my_gpu]" in findings[0].detail

    def test_plugin_exception_handled(self, tmp_path):
        def bad_plugin(ctx: CheckContext) -> list[Finding]:
            raise RuntimeError("boom")

        ctx = _make_ctx(tmp_path)
        findings = run_plugins(ctx, plugins=[("bad", bad_plugin)])
        assert len(findings) == 1
        assert findings[0].kind == "plugin_error"
        assert findings[0].severity == "warn"

    def test_multiple_plugins(self, tmp_path):
        def plugin_a(ctx: CheckContext) -> list[Finding]:
            return [Finding(kind="a", item="x", detail="from a", severity="info")]

        def plugin_b(ctx: CheckContext) -> list[Finding]:
            return [
                Finding(kind="b1", item="y", detail="from b1", severity="warn"),
                Finding(kind="b2", item="z", detail="from b2", severity="error"),
            ]

        ctx = _make_ctx(tmp_path)
        findings = run_plugins(ctx, plugins=[("a", plugin_a), ("b", plugin_b)])
        assert len(findings) == 3
        assert all("[plugin:" in f.detail for f in findings)
