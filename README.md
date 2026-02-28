# 🧰 openclaw-skill-deps

<div align="center">

**🩺 Skill-level dependency doctor for OpenClaw**

Catch missing binaries, system libraries, fonts, and version mismatches *before* a skill fails at runtime.

[![ci](https://github.com/RangeKing/openclaw-skill-deps/actions/workflows/ci.yml/badge.svg)](https://github.com/RangeKing/openclaw-skill-deps/actions/workflows/ci.yml)

**🌐 Languages:** [English](README.md) | [简体中文](README.zh-CN.md)

</div>

---

## ✨ Why this exists

OpenClaw's built-in `doctor` command checks gateway connectivity, config validity, and service health — infrastructure-level concerns. But **skill execution** frequently fails for an entirely different class of reasons:

| Failure class | Example | `doctor` catches it? |
|---|---|:---:|
| 🧱 Missing OS shared libraries | Playwright/Chromium needs `libnspr4`, `libnss3` | No |
| 🔤 Missing fonts | CJK PDF export renders tofu (□) without Noto CJK | No |
| 🧪 Missing binaries | `ffmpeg`, `pandoc`, `node`, `pdflatex` not in PATH | No |
| 📌 Binary version too old | Skill requires `node>=18`, host has `node 16` | No |
| 📦 Missing project-local deps | npm/pip packages that imply system-level deps | No |
| 🔗 Transitive native deps | `playwright` → Chromium → 13 shared `.so` libs | No |

**skill-deps-doctor** (package: `openclaw-skill-deps`) fills this gap. It is a **deterministic, offline, pre-flight check** that operates at the *skill* layer — complementary to `doctor`, not a replacement.

### 📋 How it differs from `openclaw doctor`

| | `openclaw doctor` | `skill-deps-doctor` |
|---|---|---|
| **Scope** | Gateway, config, services | Skill runtime dependencies |
| **Granularity** | System-wide | Per-skill (`SKILL.md` metadata) |
| **Checks** | Network, auth, service ports | Binaries, libs, fonts, versions |
| **Version awareness** | No | Yes (`node>=18`, `python3>=3.10`) |
| **Fix generation** | No | Yes (`--fix` generates bash/PowerShell) |
| **Cross-platform matrix** | No | Yes (`--platform-matrix` for Linux/macOS/Windows) |
| **Dependency graph** | No | Yes (`--graph tree` / `--graph dot`) |
| **CI regression gating** | No | Yes (`--baseline --fail-on-new`) |
| **Plugin system** | No | Yes (entry-point-based third-party checkers) |
| **Monorepo support** | No | Yes (`--recursive` for nested projects) |

---

## 🎯 Features

### 🔍 Core checks
- 🔎 Scan `skills/*/SKILL.md` for declared `requires.bins` and validate presence in `$PATH`
- 📌 **Version checking** — `node>=18` syntax: probes actual version and compares
- 🔤 Font detection via `fc-list` (CJK fonts for PDF export)
- 🧩 Shared library detection via `ldconfig` (Playwright/Chromium deps)
- 🔗 Transitive dependency discovery (e.g., `playwright` → 13 native `.so` libraries)
- 🎚️ Smart Playwright gating — only checks Chromium libs when skills/projects actually need them

### 🧾 Actionable output
- 📋 Copy-paste fix suggestions per platform (apt/brew/choco)
- 🔧 `--fix` generates a runnable bash/PowerShell repair script
- 📊 `--platform-matrix` shows a cross-platform fix table (Linux / macOS / Windows)
- 🔄 Auto-adapts `apt` commands to the host's package manager (dnf / yum / apk / pacman)

### 🚀 Advanced
- 🗺️ **Dependency graph**: `--graph tree` (text) or `--graph dot` (Graphviz)
- 📌 **Version-aware bins**: `bins: ["node>=18", "python3>=3.10", "ffmpeg"]`
- 📦 **Dependency profiles**: `--profile slidev`, `--profile whisper`, `--profile pdf-export`
- 📸 **Environment snapshots**: `--snapshot report.json` for reproducible diagnostics
- 🚦 **Baseline regression gating**: `--baseline old.json --fail-on-new` (exit 3 on new issues)
- ✅ **Hints schema validation**: `--validate-hints` verifies the merged YAML config
- 🔌 **Plugin contract validation**: `--validate-plugins` checks third-party checker signatures
- 📁 **Monorepo recursive scan**: `--recursive` discovers nested sub-projects

### 🔗 Ecosystem integration
- 🐍 **Programmatic API**: `from openclaw_skill_deps import run_check`
- 🔌 **Plugin system**: register custom checkers via Python entry points
- 🪃 **Pre-commit hook**: `.pre-commit-hooks.yaml` included
- ⚡ **GitHub Action**: `action.yml` with snapshot, baseline, and validation support
- 🔄 **Hints migration**: `scripts/migrate_hints_schema.py` for schema upgrades

---

## 📥 Install

From PyPI / ClawHub (recommended):

```bash
pip install openclaw-skill-deps
```

Primary CLI command: `skill-deps-doctor` (short alias: `skill-deps`).  
Legacy command `openclaw-skill-deps` remains available for backward compatibility.

For local development:

```bash
git clone https://github.com/RangeKing/openclaw-skill-deps.git
cd openclaw-skill-deps
pip install -e ".[dev]"    # Editable install with pytest + mypy
```

---

## 🧪 Usage

### Basic check

```bash
skill-deps-doctor --skills-dir ./skills
```

### 📂 Scan a project directory

```bash
skill-deps-doctor --skills-dir ./skills --check-dir ./my-project
```

### 📁 Recursive monorepo scan

```bash
skill-deps-doctor --skills-dir ./skills --check-dir ./monorepo --recursive
```

### 📦 Use a dependency profile

```bash
skill-deps-doctor --skills-dir ./skills --profile slidev --profile pdf-export
skill-deps-doctor --skills-dir ./skills --list-profiles
```

### 🔧 Generate fix script

```bash
skill-deps-doctor --skills-dir ./skills --fix > fix.sh
bash fix.sh  # review first!
```

### 🗺️ Dependency graph

```bash
skill-deps-doctor --skills-dir ./skills --graph tree
skill-deps-doctor --skills-dir ./skills --graph dot | dot -Tsvg -o deps.svg
```

### 📊 Cross-platform fix matrix

```bash
skill-deps-doctor --skills-dir ./skills --platform-matrix
```

Output:
```
+---------+------------------------------------+-------------------+--------------------+
| Item    | Linux                              | macOS             | Windows            |
+---------+------------------------------------+-------------------+--------------------+
| node    | Install Node.js (>=18) and npm     | brew install node | choco install ...  |
| ffmpeg  | sudo apt-get install -y ffmpeg     | brew install ...  | choco install ...  |
+---------+------------------------------------+-------------------+--------------------+
```

### 🤖 CI: JSON output + snapshot + baseline

```bash
# Save a baseline
skill-deps-doctor --skills-dir ./skills --json --snapshot baseline.json

# On next run, fail if new issues appeared
skill-deps-doctor --skills-dir ./skills --baseline baseline.json --fail-on-new
# Exit 0 = pass, 2 = errors, 3 = new findings vs baseline
```

### ✅ Validate hints & plugins

```bash
skill-deps-doctor --skills-dir ./skills --validate-hints
skill-deps-doctor --skills-dir ./skills --validate-plugins
```

### 🐍 Programmatic API

```python
from openclaw_skill_deps import run_check

findings = run_check("./skills", check_dir=".", profiles=["slidev"])
errors = [f for f in findings if f.severity == "error"]
```

---

## 📋 Finding schema

Each finding (in `--json` output) has:

| Field | Type | Description |
|---|---|---|
| `kind` | string | Finding category (e.g. `missing_bin`, `version_mismatch`) |
| `item` | string | Dependency identifier |
| `detail` | string | Human-readable diagnosis |
| `fix` | string? | Suggested fix command/text |
| `severity` | string | `error` \| `warn` \| `info` |
| `code` | string? | Machine-readable reason code (e.g. `MISSING_BIN`) |
| `evidence` | string? | Probe evidence snippet |
| `confidence` | string? | `high` \| `medium` \| `low` |

---

## ⚡ GitHub Action

```yaml
- uses: RangeKing/openclaw-skill-deps@v0.1.0
  with:
    skills-dir: ./skills
    check-dir: .
    profile: slidev,pdf-export
    recursive: true
    snapshot-file: .openclaw/snapshot.json
    baseline-file: .openclaw/baseline.json
    fail-on-new: true
```

## 🪃 Pre-commit hook

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/RangeKing/openclaw-skill-deps
  rev: v0.1.0
  hooks:
    - id: skill-deps-doctor
      args: [--skills-dir, ./skills, --check-dir, .]
```

## 🔌 Plugin system

Third-party checkers register via entry points:

```toml
# pyproject.toml of your plugin package
[project.entry-points."openclaw_skill_deps.checkers"]
gpu_checker = "my_plugin:check_gpu"
```

Plugin signature:

```python
from openclaw_skill_deps.models import CheckContext, Finding

def check_gpu(ctx: CheckContext) -> list[Finding]:
    ...
```

---

## 🏗️ Architecture

```
openclaw_skill_deps/
├── __init__.py       # Programmatic API (run_check)
├── models.py         # Finding, CheckContext
├── schemas.py        # Schema version constants + validation
├── parsers.py        # SKILL.md frontmatter parsing
├── scanners.py       # Project directory scanning + monorepo discovery
├── hints.py          # HintDB (YAML-backed hints, pkg manager adaptation)
├── checkers.py       # All check functions + Playwright detection
├── versions.py       # Version spec parsing, probing, comparison
├── profiles.py       # Dependency profile system
├── plugins.py        # Entry-point plugin loading + contract validation
├── fix_gen.py        # Fix script generation (bash/PowerShell)
├── graph.py          # Dependency graph + platform matrix rendering
├── snapshot.py       # Environment snapshot + baseline comparison
├── migration.py      # Hints schema migration
├── cli.py            # CLI entry point
└── data/
    └── hints.yaml    # Community-editable hint database (schema v1)
```

---

## 📄 License

MIT
