from pathlib import Path
from unittest.mock import patch

import pytest

from openclaw_skill_deps.graph import (
    DepNode,
    build_graph,
    render_dot,
    render_platform_matrix,
    render_tree,
)
from openclaw_skill_deps.hints import reset_hint_db
from openclaw_skill_deps.models import Finding


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


class TestRenderTree:
    def test_simple_tree(self):
        root = DepNode(name="my-skill", kind="skill", status="ok", children=[
            DepNode(name="node", kind="bin", status="ok", version_actual="20.11.1"),
            DepNode(name="ffmpeg", kind="bin", status="missing"),
        ])
        out = render_tree([root])
        assert "my-skill" in out
        assert "node" in out
        assert "MISSING" in out
        assert "OK" in out

    def test_nested_tree(self):
        lib = DepNode(name="libnspr4.so", kind="lib", status="unknown")
        bin_node = DepNode(name="playwright", kind="bin", status="ok", children=[lib])
        root = DepNode(name="skill-a", kind="skill", status="ok", children=[bin_node])
        out = render_tree([root])
        assert "libnspr4.so" in out

    def test_empty(self):
        out = render_tree([])
        assert out == ""


class TestRenderDot:
    def test_dot_output(self):
        root = DepNode(name="skill", kind="skill", status="ok", children=[
            DepNode(name="node", kind="bin", status="ok"),
        ])
        out = render_dot([root])
        assert out.startswith("digraph deps {")
        assert "}" in out
        assert "node" in out


class TestBuildGraph:
    @patch("openclaw_skill_deps.graph.probe_bin_version", return_value="20.11.1")
    @patch("openclaw_skill_deps.graph.which", return_value="/usr/bin/node")
    def test_basic_graph(self, _wh, _probe, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "demo", ["node>=18"])
        roots = build_graph(skills)
        assert len(roots) == 1
        assert roots[0].name == "demo"
        assert any(c.name == "node" for c in roots[0].children)

    @patch("openclaw_skill_deps.graph.which", return_value=None)
    def test_missing_bin_in_graph(self, _wh, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        _make_skill(skills, "demo", ["missing_tool"])
        roots = build_graph(skills)
        bin_nodes = [c for c in roots[0].children if c.kind == "bin"]
        assert any(c.status == "missing" for c in bin_nodes)


class TestRenderPlatformMatrix:
    def test_matrix_with_findings(self):
        findings = [
            Finding(kind="missing_bin", item="node", detail="...", severity="error"),
            Finding(kind="missing_bin", item="ffmpeg", detail="...", severity="error"),
        ]
        out = render_platform_matrix(findings)
        assert "Linux" in out
        assert "macOS" in out
        assert "Windows" in out
        assert "node" in out
        assert "ffmpeg" in out

    def test_empty_findings(self):
        out = render_platform_matrix([])
        assert "No actionable" in out

    def test_info_skipped(self):
        findings = [
            Finding(kind="version_ok", item="node", detail="ok", severity="info"),
        ]
        out = render_platform_matrix(findings)
        assert "No actionable" in out

    def test_lib_findings(self):
        findings = [
            Finding(kind="missing_lib", item="libnspr4.so", detail="...", severity="error"),
        ]
        out = render_platform_matrix(findings)
        assert "libnspr4" in out
