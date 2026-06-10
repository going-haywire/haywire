# tests/test_library_manager_dep_gating.py
"""module_name-canonical dependency matching (handoff Phase 1)."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest


def _make_manager_with_lib(*, lib_id, module_name, dist_name):
    from haybale_marketplace.library_manager import LibraryManager

    registry = MagicMock()
    registry.list_names.return_value = [lib_id]
    registry.is_library_enabled.return_value = True
    registry.get_library_distribution_name.return_value = dist_name
    identity = MagicMock()
    identity.module_name = module_name
    registry.get_library_identity.return_value = identity
    return LibraryManager(library_registry=registry)


@pytest.mark.unit
def test_dep_satisfied_by_module_name_even_when_dist_name_empty():
    """A folder-installed lib (no dist name) still satisfies a package-name dep."""
    mgr = _make_manager_with_lib(lib_id="widgets", module_name="haybale_widgets", dist_name="")
    pkg = MagicMock()
    pkg.dependencies = ["haybale_widgets"]  # canonical package-name form

    missing = mgr.get_missing_dependencies_for_package(pkg, require_enabled=False)

    assert missing == []  # recognized via module_name; NOT a false "missing"
