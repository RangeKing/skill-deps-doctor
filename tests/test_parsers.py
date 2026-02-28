from pathlib import Path

from skill_deps_doctor.parsers import SkillMeta, parse_skill_md


def _write_skill(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "SKILL.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestParseSkillMd:
    def test_valid_bins_and_install(self, tmp_path):
        md = _write_skill(tmp_path, """\
---
name: test-skill
metadata:
  clawdbot:
    requires:
      bins:
        - node
        - ffmpeg
    install:
      - id: dep1
        label: Install dep1
        bins:
          - dep1-bin
---
# Test Skill
""")
        sm = parse_skill_md(md)
        assert sm.name == "test-skill"
        assert sm.bins == ["node", "ffmpeg"]
        assert len(sm.install) == 1
        assert sm.install[0]["id"] == "dep1"

    def test_version_specs_preserved(self, tmp_path):
        md = _write_skill(tmp_path, """\
---
name: versioned
metadata:
  clawdbot:
    requires:
      bins:
        - node>=18
        - ffmpeg
        - python3==3.10.12
---
# Versioned
""")
        sm = parse_skill_md(md)
        assert sm.bins == ["node", "ffmpeg", "python3"]
        assert sm.bin_specs == ["node>=18", "ffmpeg", "python3==3.10.12"]

    def test_no_frontmatter(self, tmp_path):
        md = _write_skill(tmp_path, "# Just a heading\nNo frontmatter here.")
        sm = parse_skill_md(md)
        assert sm == SkillMeta(name=None, bins=[], install=[])

    def test_empty_metadata(self, tmp_path):
        md = _write_skill(tmp_path, """\
---
name: empty-meta
---
# Empty
""")
        sm = parse_skill_md(md)
        assert sm.name == "empty-meta"
        assert sm.bins == []
        assert sm.install == []

    def test_malformed_yaml(self, tmp_path):
        md = _write_skill(tmp_path, """\
---
name: bad
metadata: {{{invalid yaml
---
# Bad
""")
        sm = parse_skill_md(md)
        assert sm == SkillMeta(name=None, bins=[], install=[])

    def test_non_string_bins_filtered(self, tmp_path):
        md = _write_skill(tmp_path, """\
---
name: mixed
metadata:
  clawdbot:
    requires:
      bins:
        - node
        - 123
        - true
---
# Mixed
""")
        sm = parse_skill_md(md)
        assert sm.bins == ["node"]

    def test_no_clawdbot_key(self, tmp_path):
        md = _write_skill(tmp_path, """\
---
name: no-claw
metadata:
  other_tool:
    key: value
---
# No clawdbot
""")
        sm = parse_skill_md(md)
        assert sm.bins == []
        assert sm.install == []
