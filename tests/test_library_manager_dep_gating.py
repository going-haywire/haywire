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
def test_dep_satisfied_by_module_name_when_dist_name_set():
    """A pip-installed lib satisfies a dep matched by its module_name."""
    mgr = _make_manager_with_lib(
        lib_id="widgets", module_name="haybale_widgets", dist_name="haybale-widgets"
    )
    pkg = MagicMock()
    pkg.dependencies = ["haybale_widgets"]

    missing = mgr.get_missing_dependencies_for_package(pkg, require_enabled=False)

    assert missing == []


@pytest.mark.unit
def test_folder_lib_without_dist_name_does_not_satisfy_marketplace_dep():
    """A dev-barn folder lib (no dist name) does NOT satisfy a marketplace install dep.

    Without this gate, running haywire from the dev repo would let the dep check
    pass for all barn libs, silently bypassing the install guard.
    """
    mgr = _make_manager_with_lib(lib_id="widgets", module_name="haybale_widgets", dist_name="")
    pkg = MagicMock()
    pkg.dependencies = ["haybale_widgets"]

    missing = mgr.get_missing_dependencies_for_package(pkg, require_enabled=False)

    assert missing == ["haybale_widgets"]  # folder lib must NOT satisfy the gate


@pytest.mark.unit
def test_disabled_dep_blocks_install_when_require_enabled():
    """A dep that is installed but disabled is reported as missing when require_enabled=True."""
    from haybale_marketplace.library_manager import LibraryManager

    registry = MagicMock()
    registry.list_names.return_value = ["graph-editor"]
    registry.is_library_enabled.return_value = False  # installed but disabled
    registry.get_library_distribution_name.return_value = "haybale-graph-editor"
    identity = MagicMock()
    identity.module_name = "haybale_graph_editor"
    registry.get_library_identity.return_value = identity

    mgr = LibraryManager(library_registry=registry)
    pkg = MagicMock()
    pkg.dependencies = ["haybale_graph_editor"]

    missing = mgr.get_missing_dependencies_for_package(pkg, require_enabled=True)

    assert missing == ["haybale_graph_editor"]  # disabled dep must still block


@pytest.mark.unit
def test_not_installed_dep_blocks_install_when_require_enabled():
    """A dep that is not installed at all is reported as missing when require_enabled=True."""
    from haybale_marketplace.library_manager import LibraryManager

    registry = MagicMock()
    registry.list_names.return_value = []  # nothing installed
    registry.get_library_identity.return_value = MagicMock(dependencies=None)

    mgr = LibraryManager(library_registry=registry)
    pkg = MagicMock()
    pkg.dependencies = ["haybale_graph_editor"]

    missing = mgr.get_missing_dependencies_for_package(pkg, require_enabled=True)

    assert missing == ["haybale_graph_editor"]
