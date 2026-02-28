# 🧰 openclaw-skill-deps

<div align="center">

**🩺 OpenClaw 的 Skill 级依赖体检器**

在 skill 运行失败之前，提前发现：缺二进制、缺系统库、缺字体、版本不对。

[![ci](https://github.com/RangeKing/openclaw-skill-deps/actions/workflows/ci.yml/badge.svg)](https://github.com/RangeKing/openclaw-skill-deps/actions/workflows/ci.yml)

**🌐 语言：** [English](README.md) | [简体中文](README.zh-CN.md)

</div>

---

## ✨ 为什么需要它

OpenClaw 内置的 `doctor` 命令检查的是网关连接、配置合法性、服务状态——属于**基础设施级**的健康检查。但 **skill 实际执行**时，经常因为完全不同的原因失败：

| 失败类型 | 示例 | `doctor` 能发现？ |
|---|---|:---:|
| 🧱 缺系统共享库 | Playwright/Chromium 需要 `libnspr4`、`libnss3` | 否 |
| 🔤 缺字体 | 导出 PDF 时中文变"□□□"（缺 Noto CJK 字体） | 否 |
| 🧪 缺二进制 | `ffmpeg`、`pandoc`、`node`、`pdflatex` 不在 PATH | 否 |
| 📌 二进制版本太旧 | Skill 要求 `node>=18`，系统装的是 `node 16` | 否 |
| 📦 缺工程级依赖 | npm/pip 包暗含的系统原生依赖 | 否 |
| 🔗 传递原生依赖 | `playwright` → Chromium → 13 个 `.so` 共享库 | 否 |

**skill-deps-doctor**（包名：`openclaw-skill-deps`）填补的正是这个空白。它是一个**确定性、离线、预检**工具，工作在 *skill 层*——是 `doctor` 的补充，而非替代。

### 📋 与 `openclaw doctor` 的对比

| | `openclaw doctor` | `skill-deps-doctor` |
|---|---|---|
| **作用域** | 网关、配置、服务 | Skill 运行时依赖 |
| **粒度** | 系统级 | 单个 Skill（基于 `SKILL.md` 元数据） |
| **检查内容** | 网络、认证、端口 | 二进制、库、字体、版本 |
| **版本感知** | 无 | 有（`node>=18`、`python3>=3.10`） |
| **生成修复脚本** | 无 | 有（`--fix` 生成 bash/PowerShell） |
| **跨平台矩阵** | 无 | 有（`--platform-matrix` 一次看齐三平台） |
| **依赖图** | 无 | 有（`--graph tree` / `--graph dot`） |
| **CI 回归门禁** | 无 | 有（`--baseline --fail-on-new`） |
| **插件系统** | 无 | 有（entry-point 第三方 checker） |
| **Monorepo 支持** | 无 | 有（`--recursive` 递归扫描子项目） |

---

## 🎯 功能一览

### 🔍 核心检查
- 🔎 扫描 `skills/*/SKILL.md` 中声明的 `requires.bins`，验证是否在 `$PATH`
- 📌 **版本检查** — 支持 `node>=18` 语法，探测实际版本并比对
- 🔤 通过 `fc-list` 检测字体（CJK PDF 导出场景）
- 🧩 通过 `ldconfig` 检测共享库（Playwright/Chromium 依赖）
- 🔗 传递依赖发现（如 `playwright` → 13 个原生 `.so` 库）
- 🎚️ 智能 Playwright 门控 — 仅当 skill/项目真正需要时才检查 Chromium 库

### 🧾 可操作的输出
- 📋 每个平台的复制粘贴修复建议（apt / brew / choco）
- 🔧 `--fix` 生成可执行的 bash/PowerShell 修复脚本
- 📊 `--platform-matrix` 输出跨平台修复表格（Linux / macOS / Windows）
- 🔄 自动适配宿主机的包管理器（dnf / yum / apk / pacman）

### 🚀 高级能力
- 🗺️ **依赖图**：`--graph tree`（文本树）或 `--graph dot`（Graphviz DOT 格式）
- 📌 **版本约束**：`bins: ["node>=18", "python3>=3.10", "ffmpeg"]`
- 📦 **依赖 profile**：`--profile slidev`、`--profile whisper`、`--profile pdf-export`
- 📸 **环境快照**：`--snapshot report.json` 用于可复现诊断
- 🚦 **Baseline 回归门禁**：`--baseline old.json --fail-on-new`（新增问题时 exit 3）
- ✅ **Hints schema 校验**：`--validate-hints` 验证合并后的 YAML 配置
- 🔌 **插件契约校验**：`--validate-plugins` 检查第三方 checker 签名
- 📁 **Monorepo 递归扫描**：`--recursive` 自动发现嵌套子项目

### 🔗 生态集成
- 🐍 **编程 API**：`from openclaw_skill_deps import run_check`
- 🔌 **插件系统**：通过 Python entry points 注册自定义 checker
- 🪃 **Pre-commit hook**：内置 `.pre-commit-hooks.yaml`
- ⚡ **GitHub Action**：`action.yml` 支持快照、baseline、校验
- 🔄 **Hints 迁移工具**：`scripts/migrate_hints_schema.py` 用于 schema 升级

---

## 📥 安装

从 PyPI / ClawHub 安装（推荐）：

```bash
pip install openclaw-skill-deps
```

主 CLI 命令：`skill-deps-doctor`（短别名：`skill-deps`）。  
历史命令 `openclaw-skill-deps` 仍保留兼容。

本地开发：

```bash
git clone https://github.com/RangeKing/openclaw-skill-deps.git
cd openclaw-skill-deps
pip install -e ".[dev]"    # 可编辑安装，含 pytest + mypy
```

---

## 🧪 用法

### 基础检查

```bash
skill-deps-doctor --skills-dir ./skills
```

### 📂 扫描工程目录

```bash
skill-deps-doctor --skills-dir ./skills --check-dir ./my-project
```

### 📁 Monorepo 递归扫描

```bash
skill-deps-doctor --skills-dir ./skills --check-dir ./monorepo --recursive
```

### 📦 使用依赖 profile

```bash
skill-deps-doctor --skills-dir ./skills --profile slidev --profile pdf-export
skill-deps-doctor --skills-dir ./skills --list-profiles
```

### 🔧 生成修复脚本

```bash
skill-deps-doctor --skills-dir ./skills --fix > fix.sh
bash fix.sh  # 请先审核！
```

### 🗺️ 依赖图

```bash
skill-deps-doctor --skills-dir ./skills --graph tree
skill-deps-doctor --skills-dir ./skills --graph dot | dot -Tsvg -o deps.svg
```

### 📊 跨平台修复矩阵

```bash
skill-deps-doctor --skills-dir ./skills --platform-matrix
```

输出示例：
```
+---------+------------------------------------+-------------------+--------------------+
| Item    | Linux                              | macOS             | Windows            |
+---------+------------------------------------+-------------------+--------------------+
| node    | Install Node.js (>=18) and npm     | brew install node | choco install ...  |
| ffmpeg  | sudo apt-get install -y ffmpeg     | brew install ...  | choco install ...  |
+---------+------------------------------------+-------------------+--------------------+
```

### 🤖 CI：JSON 输出 + 快照 + Baseline

```bash
# 保存 baseline
skill-deps-doctor --skills-dir ./skills --json --snapshot baseline.json

# 下次运行时，若出现新问题则失败
skill-deps-doctor --skills-dir ./skills --baseline baseline.json --fail-on-new
# Exit 0 = 通过, 2 = 有错误, 3 = 相比 baseline 有新增问题
```

### ✅ 校验 hints 和插件

```bash
skill-deps-doctor --skills-dir ./skills --validate-hints
skill-deps-doctor --skills-dir ./skills --validate-plugins
```

### 🐍 编程 API

```python
from openclaw_skill_deps import run_check

findings = run_check("./skills", check_dir=".", profiles=["slidev"])
errors = [f for f in findings if f.severity == "error"]
```

---

## 📋 Finding 字段规格

每条 finding（`--json` 输出）包含：

| 字段 | 类型 | 说明 |
|---|---|---|
| `kind` | string | 问题类别（如 `missing_bin`、`version_mismatch`） |
| `item` | string | 依赖标识符 |
| `detail` | string | 人类可读的诊断信息 |
| `fix` | string? | 修复建议命令/文本 |
| `severity` | string | `error` \| `warn` \| `info` |
| `code` | string? | 机器可读原因码（如 `MISSING_BIN`） |
| `evidence` | string? | 探针证据片段 |
| `confidence` | string? | 置信度：`high` \| `medium` \| `low` |

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

## 🪃 Pre-commit Hook

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/RangeKing/openclaw-skill-deps
  rev: v0.1.0
  hooks:
    - id: skill-deps-doctor
      args: [--skills-dir, ./skills, --check-dir, .]
```

## 🔌 插件系统

第三方 checker 通过 entry points 注册：

```toml
# 你的插件包的 pyproject.toml
[project.entry-points."openclaw_skill_deps.checkers"]
gpu_checker = "my_plugin:check_gpu"
```

插件签名：

```python
from openclaw_skill_deps.models import CheckContext, Finding

def check_gpu(ctx: CheckContext) -> list[Finding]:
    ...
```

---

## 🏗️ 项目架构

```
openclaw_skill_deps/
├── __init__.py       # 编程 API (run_check)
├── models.py         # Finding, CheckContext
├── schemas.py        # Schema 版本常量 + 校验
├── parsers.py        # SKILL.md frontmatter 解析
├── scanners.py       # 项目目录扫描 + monorepo 发现
├── hints.py          # HintDB（YAML 驱动的提示数据库，包管理器适配）
├── checkers.py       # 所有检查函数 + Playwright 智能检测
├── versions.py       # 版本约束解析、探测、比较
├── profiles.py       # 依赖 profile 系统
├── plugins.py        # Entry-point 插件加载 + 契约校验
├── fix_gen.py        # 修复脚本生成（bash/PowerShell）
├── graph.py          # 依赖图 + 跨平台矩阵渲染
├── snapshot.py       # 环境快照 + baseline 对比
├── migration.py      # Hints schema 迁移
├── cli.py            # CLI 入口
└── data/
    └── hints.yaml    # 社区可编辑的提示数据库（schema v1）
```

---

## 📄 License

MIT
