# 🧰 openclaw-skill-deps

<div align="center">

**🩺 A skill-level dependency doctor for OpenClaw**

Catch missing binaries / system libs / fonts *before* a skill fails at runtime.

[![ci](https://github.com/RangeKing/openclaw-skill-deps/actions/workflows/ci.yml/badge.svg)](https://github.com/RangeKing/openclaw-skill-deps/actions/workflows/ci.yml)

**🌐 Languages / 语言：**
[English](README.md) · [简体中文](README.zh-CN.md)

</div>

---

## ✨ Why this exists (the pain point)
OpenClaw has `doctor` for gateway/config health, but **skill execution** often fails later for reasons that are hard to predict from chat:

- 🧱 **Missing OS libraries** (e.g. Playwright/Chromium deps like `libnspr4`, `libnss3`)
- 🔤 **Missing fonts** (CJK PDF export shows tofu/□ without Noto CJK)
- 🧪 **Missing binaries** (`pandoc`, `ffmpeg`, `uv`, `node`, …)
- 📦 Project-local deps missing (npm / pip packages inside a deck/project)

These failures waste cycles and produce error logs that are not actionable for most users.

---

## 🎯 What it does
A **deterministic, offline** preflight check that:

- 🔎 Scans installed skills (`skills/*/SKILL.md`) for declared `requires.bins`
- ✅ Checks whether required binaries exist in `$PATH`
- 🧩 Best-effort checks common runtime deps:
  - shared libraries (via `ldconfig` when available)
  - fonts (via `fc-list`)
- 🧾 Prints **copy/paste fixes** (e.g. `apt-get install ...`)
- 🤖 Optional `--json` output for CI/automation

> This project intentionally **does not overlap** with existing browser relay plugins or web automation projects.
> It focuses on *dependency hygiene* at the skill layer.

---

## 🚀 Install
Editable install (recommended for dev):

```bash
pip install -e .
```

---

## 🧪 Usage
Basic check (scan skills):

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills
```

Scan a project directory for presets (Node/Python/Dockerfile):

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --check-dir /path/to/project
```

Enable lightweight probes (best-effort):

- Detect Python Playwright (`pip install playwright`)
- Detect Node Playwright (`node_modules/.bin/playwright`)
- (If Node Playwright exists) run a **Chromium headless launch smoke test**

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --check-dir /path/to/project --probe
```

JSON output (good for CI):

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --json
```

Write a reproducible environment snapshot:

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --snapshot .openclaw/snapshot.json
```

Compare against a baseline and gate new issues:

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --baseline .openclaw/baseline.json --fail-on-new
```

Validate hints schema (built-in + optional overrides):

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --validate-hints
```

---

## 🧾 Output
- ❌ Missing binaries (with suggested install commands)
- ❌ Missing shared libraries (best-effort)
- ❌ Missing fonts (CJK PDF export)
- ✅ Clear next-step “Fix:” hints

JSON mode (`--json`) emits one object per finding with this stable schema:

- `kind`: finding category
- `item`: dependency identifier
- `detail`: human-readable diagnosis
- `fix`: suggested remediation command/text (nullable)
- `severity`: `error | warn | info`
- `code`: optional machine-friendly reason code
- `evidence`: optional probe evidence snippet
- `confidence`: optional confidence level (`high | medium | low`)

Snapshot mode (`--snapshot`) writes a JSON envelope with:

- `schema_version`, `created_at_utc`
- `environment` (OS family/platform/Python version)
- `inputs` (CLI parameters used for this run)
- `findings` (same finding objects as `--json`)
- Optional `baseline` comparison result (`new_findings_count`, `new_findings`)

Hints schema is versioned via top-level `schema_version` in `hints.yaml`.
Current expected version: `1`.

Plugin contract:

- Checker plugins must return `list[Finding]`
- `CheckContext.plugin_api_version` indicates the plugin API version (current: `1`)

---

## 🗺️ Roadmap
- Detect Playwright presence and run a lightweight `chromium --version` probe (best-effort)
- Add per-skill “dependency profiles” for common stacks (Slidev, Whisper, PDF tooling)
- Add `--fix` (generate a script), without auto-running privileged installs

---

## 📄 License
MIT
