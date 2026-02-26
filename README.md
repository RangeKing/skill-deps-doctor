# openclaw-skill-deps

**A skill-level dependency doctor for OpenClaw.**

## The pain point
OpenClaw has `doctor` for gateway/config health, but *skill execution* often fails later for reasons that are:
- OS libs missing (Playwright/Chromium libs like `libnspr4`, fonts like Noto CJK)
- missing binaries (`pandoc`, `ffmpeg`, `uv`, `node`, etc.)
- npm/python packages missing inside a deck/project

These failures are hard to predict from the chat UI, and they waste cycles.

## The goal
Provide a **deterministic, offline** preflight check:
- Scan installed skills (`skills/*/SKILL.md`) + a target deck/dir
- Infer required binaries and common system libs
- Output actionable fixes (apt package list, npm install hints)

This project intentionally **does not overlap** with existing browser relay plugins or web automation projects.
It’s a diagnostic tool for dependency hygiene.

## Usage
```bash
python -m openclaw_skill_deps --skills-dir /path/to/workspace/skills \
  --check-dir /path/to/deck_or_project
```

## Output
- Missing binaries (with suggested install commands)
- Missing shared libraries (best-effort via `ldconfig`/`ldd`)
- Missing fonts (CJK PDF export)
- Optional JSON output for CI

## Status
MVP: focuses on the real-world pain we hit during Slidev export (Chromium libs + fonts).

## License
MIT
