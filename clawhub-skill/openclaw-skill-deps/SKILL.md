---
name: OpenClaw Skill Deps Doctor
description: Skill-level dependency doctor for OpenClaw. Preflight check missing bins, Playwright/Chromium runtime, CJK fonts, and project presets (Node/Python/Dockerfile). Use before running skills to avoid runtime failures.
metadata: {"clawdbot": {"emoji": "🧰", "requires": {"bins": ["python3"]}, "install": [{"id": "pyyaml", "kind": "pip", "package": "pyyaml", "label": "Install PyYAML for parsing SKILL.md frontmatter"}]}}
---

# 🧰 OpenClaw Skill Deps Doctor

Use this skill to **detect missing dependencies before a skill fails**.

## What it checks
- ✅ Binaries required by installed skills (`metadata.clawdbot.requires.bins`)
- ✅ Skill `metadata.clawdbot.install` arrays (validates declared `bins` exist)
- ✅ CJK fonts (prevents PDF tofu/□)
- ✅ Playwright probes (Node + Python) + Chromium headless launch smoke test (best-effort)
- ✅ Project presets via `--check-dir`:
  - Node: `package.json`
  - Python: `pyproject.toml` / `requirements.txt`
  - Docker: `Dockerfile` (also extracts apt/apk packages for hints)

## Install deps
This skill requires PyYAML:

```bash
pip install pyyaml
```

## Run
```bash
python {baseDir}/scripts/openclaw-skill-deps.py \
  --skills-dir /path/to/workspace/skills \
  --check-dir /path/to/project \
  --probe
```

JSON output (for CI):
```bash
python {baseDir}/scripts/openclaw-skill-deps.py --skills-dir /path/to/workspace/skills --json
```

## Notes
- Linux-only: shared-lib checks for Chromium runtime (via `ldconfig`).
- macOS/Windows: Playwright checks rely on probes instead.
