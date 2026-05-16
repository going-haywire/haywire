"""Smoke test: GraphAppState appears in app_data after library load.

Marks the boundary where the new library is wired into the framework's
discovery + state-container lifecycle. Mirrors the pattern used in
``tests/haystack/test_haystack_state.py`` — see that file for the
canonical setup if this test needs deeper assertions later.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="Stub — flesh out using existing app-boot integration patterns from tests/haystack")
def test_graph_app_state_loads_via_library_system(tmp_path):
    """Booting HaywireApp with haybale-graph-editor enabled puts
    GraphAppState into app_data.

    Contract:
      - workspace_root = tmp_path
      - HaywireApp constructed; library system discovers
        haybale-graph-editor via entry-points and runs
        Library.register_components()
      - LibraryStateContainer holds an instance of GraphAppState whose
        on_enable has fired (the default no-op is fine)
      - context.app_data[GraphAppState] is the same instance
    """
