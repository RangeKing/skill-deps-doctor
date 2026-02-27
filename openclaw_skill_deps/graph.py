from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .hints import get_hint_db, os_family, which
from .models import Finding
from .parsers import parse_skill_md
from .versions import VersionReq, compare_versions, parse_bin_spec, probe_bin_version


@dataclass
class DepNode:
    name: str
    kind: str  # "bin", "lib", "font", "package"
    status: str = "unknown"  # "ok", "missing", "version_mismatch", "unknown"
    version_actual: str | None = None
    version_req: str | None = None
    children: list[DepNode] = field(default_factory=list)


def build_graph(skills_dir: Path, check_dir: Path | None = None) -> list[DepNode]:
    """Build a dependency tree rooted per skill."""
    db = get_hint_db()
    roots: list[DepNode] = []

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        sm = parse_skill_md(skill_md)
        skill_name = sm.name or skill_md.parent.name
        skill_node = DepNode(name=skill_name, kind="skill", status="ok")

        for spec in sm.bin_specs:
            vr = parse_bin_spec(spec)
            bin_node = _bin_node(vr)

            trans_libs = db.transitive_libs(vr.name)
            if os_family() == "linux" and trans_libs:
                for lib in trans_libs:
                    bin_node.children.append(_lib_node(lib))

            skill_node.children.append(bin_node)

        for font_name in db.font_hints:
            skill_node.children.append(
                DepNode(name=font_name, kind="font", status="unknown")
            )

        roots.append(skill_node)

    if check_dir:
        _add_project_deps(roots, check_dir, db)

    return roots


def _bin_node(vr: VersionReq) -> DepNode:
    path = which(vr.name)
    if path is None:
        return DepNode(
            name=vr.name, kind="bin", status="missing",
            version_req=f"{vr.operator}{vr.version}" if vr.has_constraint else None,
        )
    actual = probe_bin_version(vr.name)
    if vr.has_constraint and actual:
        assert vr.operator is not None and vr.version is not None
        ok = compare_versions(actual, vr.operator, vr.version)
        return DepNode(
            name=vr.name, kind="bin",
            status="ok" if ok else "version_mismatch",
            version_actual=actual,
            version_req=f"{vr.operator}{vr.version}",
        )
    return DepNode(
        name=vr.name, kind="bin", status="ok",
        version_actual=actual,
        version_req=f"{vr.operator}{vr.version}" if vr.has_constraint else None,
    )


def _lib_node(so: str) -> DepNode:
    return DepNode(name=so, kind="lib", status="unknown")


def _add_project_deps(
    roots: list[DepNode],
    check_dir: Path,
    db: object,
) -> None:
    pkg_json = check_dir / "package.json"
    if pkg_json.exists():
        import json
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            for key in ("dependencies", "devDependencies"):
                for pkg in data.get(key, {}):
                    node = DepNode(name=f"npm:{pkg}", kind="package", status="ok")
                    if roots:
                        roots[0].children.append(node)
        except Exception:
            pass


_STATUS_MARKS = {
    "ok": "OK",
    "missing": "MISSING",
    "version_mismatch": "MISMATCH",
    "unknown": "?",
}


def render_tree(roots: list[DepNode]) -> str:
    """Render the graph as a text tree."""
    lines: list[str] = []
    for i, root in enumerate(roots):
        is_last_root = i == len(roots) - 1
        _render(root, lines, prefix="", is_last=is_last_root, is_root=True)
    return "\n".join(lines)


def _render(
    node: DepNode,
    lines: list[str],
    prefix: str,
    is_last: bool,
    is_root: bool = False,
) -> None:
    connector = "" if is_root else ("+-- " if is_last else "+-- ")
    label = _label(node)
    lines.append(f"{prefix}{connector}{label}")

    child_prefix = prefix + ("" if is_root else ("    " if is_last else "|   "))
    for j, child in enumerate(node.children):
        _render(child, lines, child_prefix, j == len(node.children) - 1)


def _label(n: DepNode) -> str:
    mark = _STATUS_MARKS.get(n.status, "?")
    ver = ""
    if n.version_actual:
        ver = f" v{n.version_actual}"
    req = ""
    if n.version_req:
        req = f" (need {n.version_req})"
    if n.kind == "skill":
        return n.name
    return f"{n.name}{ver}{req} [{mark}]"


def render_dot(roots: list[DepNode]) -> str:
    """Render the graph in Graphviz DOT format."""
    lines = ["digraph deps {", '  rankdir=LR;', '  node [shape=box];']
    _counter = [0]

    def _id() -> str:
        _counter[0] += 1
        return f"n{_counter[0]}"

    def _emit(node: DepNode, parent_id: str | None) -> None:
        nid = _id()
        color = {"ok": "green", "missing": "red", "version_mismatch": "orange"}.get(
            node.status, "gray"
        )
        label = _label(node).replace('"', '\\"')
        lines.append(f'  {nid} [label="{label}" color="{color}"];')
        if parent_id:
            lines.append(f"  {parent_id} -> {nid};")
        for child in node.children:
            _emit(child, nid)

    for root in roots:
        _emit(root, None)

    lines.append("}")
    return "\n".join(lines)


def render_platform_matrix(findings: list[Finding]) -> str:
    """Render a multi-platform fix matrix for all error/warn findings."""
    db = get_hint_db()
    rows: list[tuple[str, str, str, str]] = []

    for f in findings:
        if f.severity == "info":
            continue
        if f.kind in ("missing_bin", "missing_install_bin"):
            fixes = db.all_bin_fixes(f.item)
            rows.append((
                f.item,
                fixes.get("linux") or "-",
                fixes.get("macos") or "-",
                fixes.get("windows") or "-",
            ))
        elif f.kind == "missing_font":
            fix_l = db.fix_for_font(f.item) if os_family() == "linux" else (
                db.font_hints.get(f.item, {}).get("linux") or "-"
            )
            fix_m = db.font_hints.get(f.item, {}).get("macos") or "-"
            fix_w = db.font_hints.get(f.item, {}).get("windows") or "-"
            rows.append((f.item, fix_l or "-", fix_m or "-", fix_w or "-"))
        elif f.kind in ("missing_lib", "transitive_missing_lib"):
            apt = db.fix_for_lib(f.item) or "-"
            rows.append((f.item, apt, "(N/A)", "(N/A)"))

    if not rows:
        return "No actionable findings for platform matrix."

    header = ("Item", "Linux", "macOS", "Windows")
    all_rows = [header] + rows
    widths = [max(len(r[i]) for r in all_rows) for i in range(4)]

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    lines = [sep]
    for idx, row in enumerate(all_rows):
        cells = " | ".join(row[i].ljust(widths[i]) for i in range(4))
        lines.append(f"| {cells} |")
        if idx == 0:
            lines.append(sep)
    lines.append(sep)
    return "\n".join(lines)
