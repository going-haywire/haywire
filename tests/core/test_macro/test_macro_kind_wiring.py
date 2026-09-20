"""The macro kind is wired into the maps every kind-generic consumer reads."""

import pytest

pytestmark = pytest.mark.unit


def test_the_kind_maps_to_the_macro_registry():
    from haywire.core.library.kinds import kind_registry_map
    from haywire.core.macro.registry import MacroRegistry

    assert kind_registry_map()["macro"] is MacroRegistry


def test_the_kind_maps_to_the_macros_folder():
    from haywire.core.library.kinds import KIND_FOLDERS

    assert KIND_FOLDERS["macro"] == "macros"


def test_the_kind_has_a_canon_area():
    from haywire.core.library.kinds import canon_area

    assert canon_area("macro") == "macros"


def test_macros_scan_after_nodes():
    """Containment reads node classes, so NodeRegistry (70) must be populated first."""
    from haywire.core.library.base import BaseLibrary

    priority = BaseLibrary._REGISTRY_SCAN_PRIORITY
    assert priority["MacroRegistry"] == 75
    assert priority["NodeRegistry"] < priority["MacroRegistry"]
