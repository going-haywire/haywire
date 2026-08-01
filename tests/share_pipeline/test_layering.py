"""The share package's layering, enforced.

Replaces the hand-run `python -c "import haywire_studio.share"` check that
guarded the old import-cycle rule. Cycles are now prevented structurally: no
module inside the package imports the package root, so the root's re-exports
cannot loop back.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

_SHARE_ROOT = Path(__file__).resolve().parents[2] / "packages/haywire-studio/src/haywire_studio/share"


def _module_imports(path: Path) -> set[str]:
    """Every module this file imports, as dotted names.

    Includes relative imports (``node.level > 0``) resolved to their
    absolute form, and ``from haywire_studio import share``-style imports
    (which bind the package root under a different attribute path than
    ``from haywire_studio.share import X``) — both are as capable of
    recreating the cycle as the plain ``import haywire_studio.share`` form.
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
                # its position under _SHARE_ROOT.
                package_parts = path.relative_to(_SHARE_ROOT).parent.parts
                base_parts = (
                    package_parts[: len(package_parts) - (node.level - 1)]
                    if node.level > 1
                    else package_parts
                )
                base = ".".join(["haywire_studio", "share", *base_parts])
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

    An internal module importing `haywire_studio.share` would run the root
    __init__, which imports every submodule — the exact loop that made the
    old share.py/share_pipeline pair circular.
    """
    offenders: list[str] = []
    for path in sorted(_SHARE_ROOT.rglob("*.py")):
        if path.name == "__init__.py" and path.parent == _SHARE_ROOT:
            continue  # the root itself is allowed to import its submodules
        if "haywire_studio.share" in _module_imports(path):
            offenders.append(str(path.relative_to(_SHARE_ROOT)))
    assert offenders == [], f"these import the package root: {offenders}"


def test_leaf_modules_have_no_in_package_dependencies() -> None:
    """git.py and barn.py are the bottom layer: everything may depend on
    them, so they must depend on nothing here."""
    for leaf in ("git.py", "barn.py"):
        imports = _module_imports(_SHARE_ROOT / leaf)
        internal = {name for name in imports if name.startswith("haywire_studio")}
        assert internal == set(), f"{leaf} must not import {internal}"


def test_every_share_module_imports_standalone() -> None:
    """Each module must import in a fresh interpreter without its siblings
    being imported first — the regression the old §5 rule guarded by hand."""
    modules = []
    for path in sorted(_SHARE_ROOT.rglob("*.py")):
        rel = path.relative_to(_SHARE_ROOT).with_suffix("")
        parts = [p for p in rel.parts if p != "__init__"]
        modules.append(".".join(["haywire_studio.share", *parts]))

    for name in modules:
        result = subprocess.run(
            [sys.executable, "-c", f"import {name}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"{name} failed to import:\n{result.stderr}"
