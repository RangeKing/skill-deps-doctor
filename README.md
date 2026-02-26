# 🧰 openclaw-skill-deps

<div align="center">

**🩺 A skill-level dependency doctor for OpenClaw**

Catch missing binaries / system libs / fonts *before* a skill fails at runtime.

[![ci](./.github/workflows/ci.yml/badge.svg)](./.github/workflows/ci.yml)

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

JSON output (good for CI):

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --json
```

---

## 🧾 Output
- ❌ Missing binaries (with suggested install commands)
- ❌ Missing shared libraries (best-effort)
- ❌ Missing fonts (CJK PDF export)
- ✅ Clear next-step “Fix:” hints

---

## 🗺️ Roadmap
- Detect Playwright presence and run a lightweight `chromium --version` probe (best-effort)
- Add per-skill “dependency profiles” for common stacks (Slidev, Whisper, PDF tooling)
- Add `--fix` (generate a script), without auto-running privileged installs

---

## 📄 License
MIT
