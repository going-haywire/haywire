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
        edit = SimpleNamespace(selected_nodes=set(nodes), selected_edges=set(edges), active_node=None)
        data = MagicMock()
        data.__getitem__.return_value = edit
        return SimpleNamespace(data=data)

    return _make


from tests.core.test_macro.test_detach_placement import macro_folder  # noqa: E402, F401


@pytest.fixture(autouse=True)
def _own_ambient_di(library_system):
    """Point the ambient DI context at the session library system for each test.

    A session-scoped server elsewhere (the farmhand harness) leaves its own factories
    ambient (library system, factories), so a placement built here would look its macro up in
    a registry the ``macro_folder`` fixture never touched.
    """
    from haywire.core.di import context as di_context
    from haywire.core.di.config import set_global_injector, set_library_system
    from tests.conftest import _restore_ambient_di, _snapshot_ambient_di

    snap = _snapshot_ambient_di()
    set_library_system(library_system)
    set_global_injector(library_system.injector)
    di_context.set_node_factory(library_system.get_node_factory())
    di_context.set_adapter_factory(library_system.get_adapter_factory())
    di_context.set_type_registry(library_system.get_type_registry())
    di_context.set_settings_registry(library_system.get_settings_registry())
    yield
    _restore_ambient_di(snap)
