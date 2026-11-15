"""The Author API's name lists, enforced (ADR 0084).

A name leaves ``haywire.api`` or ``haywire.api.workbench`` only by an edit to
``tests/api/names.py``, which shows the break in review.
"""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

import haywire.api as component
import haywire.api.workbench as workbench
from haywire.barn.builtin import types as builtin_types
from haywire.barn.builtin import widget_keys as builtin_widget_keys
from haywire.barn.builtin import widgets as builtin_widgets
from tests.api import names


@pytest.mark.parametrize(
    ("module", "expected"),
    [(component, names.COMPONENT), (workbench, names.WORKBENCH)],
    ids=["component", "workbench"],
)
def test_all_matches_the_checked_in_list(module, expected) -> None:
    assert sorted(module.__all__) == expected


@pytest.mark.parametrize(
    ("module", "expected"),
    [(component, names.COMPONENT_DEPRECATED), (workbench, names.WORKBENCH_DEPRECATED)],
    ids=["component", "workbench"],
)
def test_deprecated_names_match_the_checked_in_list(module, expected) -> None:
    """A deprecated name cannot vanish before its window ends, and is no longer in ``__all__``."""
    assert sorted(module._DEPRECATED) == expected
    assert set(module._DEPRECATED) & set(module.__all__) == set()
    for entry in module._DEPRECATED.values():
        module_path, _, attribute = entry.target.partition(":")
        assert hasattr(importlib.import_module(module_path), attribute)
        assert entry.removed_in


@pytest.mark.parametrize("module", [component, workbench], ids=["component", "workbench"])
def test_every_name_resolves_and_is_listed_once(module) -> None:
    assert len(set(module.__all__)) == len(module.__all__)
    missing = [name for name in module.__all__ if not hasattr(module, name)]
    assert missing == []


def test_no_name_means_two_things() -> None:
    """A name in both modules must be the same object in both."""
    shared = set(component.__all__) & set(workbench.__all__)
    different = [n for n in shared if getattr(component, n) is not getattr(workbench, n)]
    assert different == []


@pytest.mark.parametrize(
    "names_of_block",
    [
        builtin_types.__all__,
        builtin_widgets.__all__,
        [n for n in vars(builtin_widget_keys) if n.endswith("_WIDGET")],
    ],
    ids=["types", "widgets", "widget_keys"],
)
def test_a_builtin_block_is_exported_whole(names_of_block) -> None:
    """A builtin type or widget is never half public: its whole module is exported."""
    assert set(names_of_block) - set(component.__all__) == set()


@pytest.mark.parametrize("module", ["haywire.api", "haywire.api.workbench"])
def test_imports_first_in_a_fresh_interpreter(module) -> None:
    """An author's first haywire import is this module: it must not depend on import order."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"], capture_output=True, text=True, timeout=110
    )
    assert result.returncode == 0, result.stderr
