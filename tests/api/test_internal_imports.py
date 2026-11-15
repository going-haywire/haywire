"""What each library in ``barn/`` still imports from the framework's internals (ADR 0084).

A library imports the framework through ``haywire.api`` and
``haywire.api.workbench``. A workbench or test library may still reach into
``haywire.core``, ``haywire.ui`` and ``haywire.barn``; ``allowlist.py`` holds
every such import. The test fails when a library gains one and when a listed
one is gone, so the lists only shrink.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.api.allowlist import INTERNAL_IMPORTS

_BARN = Path(__file__).resolve().parents[2] / "barn"
_INTERNAL = ("haywire.core", "haywire.ui", "haywire.barn")


def _is_internal(module: str) -> bool:
    return any(module == root or module.startswith(root + ".") for root in _INTERNAL)


def internal_imports(library: str) -> set[str]:
    """Every internal import of a library, as ``module:name`` (``module`` alone for ``import module``)."""
    found: set[str] = set()
    for path in sorted((_BARN / library).rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and not node.level and _is_internal(node.module or ""):
                found.update(f"{node.module}:{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names if _is_internal(alias.name))
    return found


@pytest.mark.parametrize("library", sorted(INTERNAL_IMPORTS))
def test_a_library_imports_only_its_listed_internals(library) -> None:
    actual = internal_imports(library)
    listed = set(INTERNAL_IMPORTS[library])
    assert actual - listed == set(), "new internal imports: use haywire.api, or decide the name (ADR 0084)"
    assert listed - actual == set(), "no longer imported: remove them from tests/api/allowlist.py"


def test_every_library_is_listed() -> None:
    libraries = {p.name for p in _BARN.iterdir() if p.is_dir() and (p / "pyproject.toml").exists()}
    assert libraries == set(INTERNAL_IMPORTS)
