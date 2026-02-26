# 🧰 openclaw-skill-deps

<div align="center">

**🩺 OpenClaw 的 Skill 依赖体检器（技能级 Doctor）**

在 skill 真正执行失败之前，提前发现：缺二进制 / 缺系统库 / 缺字体。

[![ci](./.github/workflows/ci.yml/badge.svg)](./.github/workflows/ci.yml)

**🌐 语言 / Languages：**
[English](README.md) · [简体中文](README.zh-CN.md)

</div>

---

## ✨ 为什么需要它（痛点）
OpenClaw 有 `doctor` 用来检查网关/配置健康，但在实际使用中，**skill 的执行**经常会在最后一步才失败，常见原因是：

- 🧱 **缺系统库**（例如 Playwright/Chromium 运行库：`libnspr4`、`libnss3`）
- 🔤 **缺字体**（导出 PDF 时中文变“口口口/□”，常见是缺 Noto CJK）
- 🧪 **缺二进制**（`pandoc`、`ffmpeg`、`uv`、`node` 等）
- 📦 工程目录里缺 npm/pip 依赖（deck/project 本地依赖没装）

这类问题对用户来说往往是“看不懂的错误堆栈”，会大量浪费排查时间。

---

## 🎯 它做什么
一个**确定性、离线**的预检工具：

- 🔎 扫描已安装 skills（`skills/*/SKILL.md`）里声明的 `requires.bins`
- ✅ 检查这些 bin 是否在 `$PATH`
- 🧩 尽力检查常见运行依赖：
  - 共享库（尽力通过 `ldconfig`）
  - 字体（通过 `fc-list`）
- 🧾 输出可复制的修复建议（如 `apt-get install ...`）
- 🤖 支持 `--json` 输出，方便 CI/自动化 gate

> 本项目刻意**不去做**浏览器接管、网页自动化、爬虫等能力，避免与现有知名插件/开源项目重叠。
> 它只解决一个问题：**skill 依赖卫生（dependency hygiene）**。

---

## 🚀 安装
开发/本地可编辑安装：

```bash
pip install -e .
```

---

## 🧪 用法
基础检查：

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills
```

扫描工程目录预设（Node/Python/Dockerfile）：

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --check-dir /path/to/project
```

开启轻量探针（best-effort）：

- 检测 Python Playwright（`pip install playwright`）
- 检测 Node Playwright（`node_modules/.bin/playwright`）
- （如果存在 Node Playwright）尝试进行一次 **Chromium 无头启动 smoke test**

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --check-dir /path/to/project --probe
```

JSON 输出（CI 推荐）：

```bash
openclaw-skill-deps --skills-dir /path/to/workspace/skills --json
```

---

## 🧾 输出内容
- ❌ 缺失二进制（附修复建议）
- ❌ 缺失共享库（best-effort）
- ❌ 缺失字体（CJK PDF 导出）
- ✅ 明确的“下一步怎么修”提示

---

## 🗺️ Roadmap
- 检测 Playwright/Chromium 并做轻量探针（best-effort）
- 为常见 skill 栈提供“依赖模板”（Slidev / Whisper / PDF 等）
- 增加 `--fix`：生成修复脚本（不自动执行 sudo）

---

## 📄 License
MIT
