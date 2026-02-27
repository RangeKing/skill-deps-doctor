from __future__ import annotations

import inspect
import importlib.metadata
import logging
from typing import Callable

from .models import CheckContext, Finding
from .schemas import PLUGIN_API_VERSION

logger = logging.getLogger(__name__)

PluginFunc = Callable[[CheckContext], list[Finding]]


def load_plugins() -> list[tuple[str, PluginFunc]]:
    """Discover checker plugins registered via the entry-point group
    ``openclaw_skill_deps.checkers``.

    Each entry point must resolve to a callable with signature::

        def my_checker(ctx: CheckContext) -> list[Finding]: ...

    Returns a list of ``(name, callable)`` pairs.
    """
    plugins: list[tuple[str, PluginFunc]] = []

    eps = importlib.metadata.entry_points(
        group="openclaw_skill_deps.checkers",
    )

    for ep in eps:
        try:
            func = ep.load()
            if callable(func):
                plugins.append((ep.name, func))
            else:
                logger.warning("Plugin %r is not callable, skipping", ep.name)
        except Exception:
            logger.warning("Failed to load plugin %r, skipping", ep.name, exc_info=True)

    return plugins


def run_plugins(
    ctx: CheckContext,
    plugins: list[tuple[str, PluginFunc]] | None = None,
) -> list[Finding]:
    """Run all discovered (or provided) plugins and collect findings."""
    if plugins is None:
        plugins = load_plugins()

    findings: list[Finding] = []
    for name, func in plugins:
        try:
            results = func(ctx)
            if not isinstance(results, list):
                findings.append(
                    Finding(
                        kind="plugin_invalid_result",
                        item=name,
                        detail=(
                            f"[plugin:{name}] expected list[Finding], got "
                            f"{type(results).__name__}"
                        ),
                        severity="warn",
                        code="PLUGIN_RESULT_INVALID",
                        confidence="high",
                    )
                )
                continue

            for idx, f in enumerate(results):
                if not isinstance(f, Finding):
                    findings.append(
                        Finding(
                            kind="plugin_invalid_result",
                            item=name,
                            detail=(
                                f"[plugin:{name}] result[{idx}] is "
                                f"{type(f).__name__}, expected Finding"
                            ),
                            severity="warn",
                            code="PLUGIN_RESULT_INVALID",
                            confidence="high",
                        )
                    )
                    continue
                if not f.detail.startswith(f"[plugin:{name}]"):
                    f.detail = f"[plugin:{name}] {f.detail}"
                findings.append(f)
        except Exception:
            logger.warning("Plugin %r raised an exception", name, exc_info=True)
            findings.append(
                Finding(
                    kind="plugin_error",
                    item=name,
                    detail=f"[plugin:{name}] plugin raised an exception",
                    severity="warn",
                )
            )
    return findings


def plugin_api_version() -> int:
    return PLUGIN_API_VERSION


def validate_plugins_contract(
    ctx: CheckContext,
) -> list[Finding]:
    """Validate plugin entry points and callable contracts without executing plugins."""
    findings: list[Finding] = []
    eps = importlib.metadata.entry_points(group="openclaw_skill_deps.checkers")

    if not eps:
        return [
            Finding(
                kind="plugin_validation_info",
                item="plugins",
                detail="No checker plugins registered in entry-point group 'openclaw_skill_deps.checkers'",
                severity="info",
                code="PLUGIN_NONE",
                confidence="high",
            )
        ]

    for ep in eps:
        try:
            func = ep.load()
        except Exception as e:
            findings.append(
                Finding(
                    kind="plugin_contract_error",
                    item=ep.name,
                    detail=f"Failed to load plugin entry point '{ep.value}': {e}",
                    severity="error",
                    code="PLUGIN_LOAD_FAILED",
                    confidence="high",
                )
            )
            continue

        if not callable(func):
            findings.append(
                Finding(
                    kind="plugin_contract_error",
                    item=ep.name,
                    detail=f"Entry point '{ep.value}' resolved to non-callable {type(func).__name__}",
                    severity="error",
                    code="PLUGIN_NOT_CALLABLE",
                    confidence="high",
                )
            )
            continue

        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError) as e:
            findings.append(
                Finding(
                    kind="plugin_contract_error",
                    item=ep.name,
                    detail=f"Unable to inspect plugin signature: {e}",
                    severity="error",
                    code="PLUGIN_SIGNATURE_UNKNOWN",
                    confidence="high",
                )
            )
            continue

        try:
            sig.bind(ctx)
        except TypeError as e:
            findings.append(
                Finding(
                    kind="plugin_contract_error",
                    item=ep.name,
                    detail=(
                        "Plugin signature must accept one CheckContext argument; "
                        f"got signature {sig}: {e}"
                    ),
                    severity="error",
                    code="PLUGIN_SIGNATURE_INVALID",
                    confidence="high",
                )
            )
            continue

        ret = sig.return_annotation
        if ret is not inspect.Signature.empty and not _return_annotation_looks_like_finding_list(ret):
            findings.append(
                Finding(
                    kind="plugin_contract_warning",
                    item=ep.name,
                    detail=(
                        "Return annotation should be list[Finding]; "
                        f"got '{ret}'"
                    ),
                    severity="warn",
                    code="PLUGIN_RETURN_ANNOTATION_WEAK",
                    confidence="medium",
                )
            )

    if not findings:
        findings.append(
            Finding(
                kind="plugin_validation_info",
                item="plugins",
                detail=f"Plugin contract validation passed for {len(eps)} plugin(s)",
                severity="info",
                code="PLUGIN_CONTRACT_OK",
                confidence="high",
            )
        )
    return findings


def _return_annotation_looks_like_finding_list(annotation: object) -> bool:
    text = str(annotation).replace(" ", "")
    if text in {"list", "typing.List"}:
        return True
    if "Finding" in text and ("list[" in text or "List[" in text):
        return True
    return False
