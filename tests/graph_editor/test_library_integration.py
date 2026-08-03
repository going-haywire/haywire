"""Smoke test: GraphAppState appears in the state container after library load.

Marks the boundary where the new library is wired into the framework's
discovery + state-container lifecycle. Mirrors the pattern used in
``tests/haystack/test_haystack_state.py`` — see that file for the
canonical setup if this test needs deeper assertions later.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_graph_app_state_loads_via_library_system(library_system):
    """Booting the library system registers GraphAppState in the container.

    Every other GraphAppState test constructs the class directly, so this is
    the only coverage of the discovery path: entry-point scan →
    ``Library.register_components()`` → state container. A registration
    regression would leave those unit tests green.
    """
    from haywire.core.state import LibraryStateContainer
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    container = library_system.injector.get(LibraryStateContainer)
    instance = container.get(GraphAppState)

    assert instance is not None, "GraphAppState was not registered by the library system"
    assert isinstance(instance, GraphAppState)
    # on_enable has run: the registry it owns is usable, not a half-built object.
    assert instance.get("nonexistent-graph-id") is None
