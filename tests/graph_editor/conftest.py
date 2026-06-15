from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def make_ctx_with_selection():
    """Return a factory that builds a minimal SessionContext stub with selection state.

    Uses the same SimpleNamespace pattern as test_selection_panels_unified.py so
    the stub satisfies ctx.data[EditState] lookups without a real DI container.
    """

    def _make(nodes, edges):
        edit = SimpleNamespace(selected_nodes=set(nodes), selected_edges=set(edges))
        data = MagicMock()
        data.__getitem__.return_value = edit
        return SimpleNamespace(data=data)

    return _make
