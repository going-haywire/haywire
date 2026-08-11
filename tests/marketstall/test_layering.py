"""Marketstall's layering, enforced.

Mirrors ``tests/share_pipeline/test_layering.py``: no module inside the
package imports the package root, so the root's re-exports cannot loop back.
Added alongside the move of ``Haybale``/``Deprecation`` out of this package
(see ``internals/handoff/haybale-record-move-out-of-marketstall.md``), which
touched every internal file's imports anyway — the cheapest moment to close
a gap marketstall never had a guard for.

This asserts ONLY that ``core/marketstall/`` is free of self-imports. It does
NOT assert that ``core.library`` is free of marketstall imports —
``dep_edit.py`` legitimately imports ``marketstall.requirement`` at module
scope, and that is out of scope for this guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MARKETSTALL_ROOT = (
    Path(__file__).resolve().parents[2] / "packages/haywire-core/src/haywire/core/marketstall"
)


def _module_imports(path: Path) -> set[str]:
    """Every module this file imports, as dotted names.

    Includes relative imports (``node.level > 0``) resolved to their
    absolute form — as capable of recreating a self-import as the plain
    ``import haywire.core.marketstall`` form.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    found.add(node.module)
                    for alias in node.names:
                        found.add(f"{node.module}.{alias.name}")
            else:
                # Relative to this file's own package — resolve against
                # its position under _MARKETSTALL_ROOT.
                package_parts = path.relative_to(_MARKETSTALL_ROOT).parent.parts
                base_parts = (
                    package_parts[: len(package_parts) - (node.level - 1)]
                    if node.level > 1
                    else package_parts
                )
                base = ".".join(["haywire", "core", "marketstall", *base_parts])
                if node.module:
                    found.add(f"{base}.{node.module}")
                else:
                    for alias in node.names:
                        found.add(f"{base}.{alias.name}")
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_no_internal_module_imports_the_package_root() -> None:
    """The re-exports in __init__ must stay one-directional.

    An internal module importing `haywire.core.marketstall` would run the
    root __init__, which imports every submodule — the exact loop
    `tests/share_pipeline/test_layering.py` was written to prevent for
    `publishing`.
    """
    offenders: list[str] = []
    for path in sorted(_MARKETSTALL_ROOT.rglob("*.py")):
        if path.name == "__init__.py" and path.parent == _MARKETSTALL_ROOT:
            continue  # the root itself is allowed to import its submodules
        if "haywire.core.marketstall" in _module_imports(path):
            offenders.append(str(path.relative_to(_MARKETSTALL_ROOT)))
    assert offenders == [], f"these import the package root: {offenders}"
