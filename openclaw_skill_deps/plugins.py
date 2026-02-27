from __future__ import annotations

import importlib.metadata
import logging
from typing import Callable

from .models import CheckContext, Finding

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
            for f in results:
                if not f.detail.startswith(f"[plugin:{name}]"):
                    f.detail = f"[plugin:{name}] {f.detail}"
            findings.extend(results)
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
