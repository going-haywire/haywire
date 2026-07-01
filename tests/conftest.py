"""
Root pytest configuration with DI fixtures.

Provides fixtures for different test scopes and scenarios.
"""

import importlib
from pathlib import Path
from typing import Callable, Generator

import pytest
from injector import Injector

from haywire.core.di.test_config import create_test_injector, create_test_library_system

# IMPORTANT: Import order matters due to circular dependencies
# Import graph module first to resolve circular imports
from haywire.core.graph.editor import Editor  # noqa: F401
from haywire.core.graph.base import BaseGraph  # noqa: F401

# Import types only when needed to avoid circular imports
from haywire.core.node.registry import NodeRegistry
from haywire.core.node.factory import NodeFactory
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.adapter.factory import AdapterFactory
from haywire.core.types.registry import TypeRegistry
from haywire.core.state import LibraryStateContainer
from haywire.core.undo.interfaces import IHistoryManager
from haywire.core.undo.history_manager import HistoryManager
from haywire.core.undo.config import UndoConfig


# ==============================================================================
# Pytest Configuration
# ==============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (slower, full system)")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "ui: UI-related tests")
    config.addinivalue_line("markers", "core: Core functionality tests")


# ==============================================================================
# NiceGUI global-state reset
#
# user_simulation() (used by test_library_operation_progress_modal) starts a
# NiceGUI event loop, sets core.script_mode=True, and leaves stale entries in
# Slot.stacks keyed by the asyncio task that ran during the simulation.  Any
# subsequent test that calls Client() outside an event loop then fails with
# "The parent element this slot belongs to has been deleted" because
# context.slot resolves to a dead slot from the previous simulation.
#
# This autouse fixture resets all three pieces of shared NiceGUI state after
# every test so the next test always starts from a clean slate.
# ==============================================================================


@pytest.fixture(autouse=True)
def _reset_nicegui_globals():
    yield
    try:
        from nicegui import core
        from nicegui.slot import Slot

        Slot.stacks.clear()
        core.script_mode = False
        core.script_client = None
    except Exception:
        pass


# ==============================================================================
# Path Fixtures
# ==============================================================================


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get the project root directory."""
    # Walk up from tests/ to find pyproject.toml
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


@pytest.fixture(scope="session")
def test_library_path(project_root: Path) -> Path:
    """Get path to test libraries."""
    return project_root / "barn"


# ==============================================================================
# DI Injector Fixtures
# ==============================================================================


@pytest.fixture(scope="function")
def test_injector(project_root: Path) -> Generator[Injector, None, None]:
    """
    Provide a fresh test injector for each test.

    This is for unit tests that need DI but not full library loading.
    """
    injector = create_test_injector(
        workspace_root=str(project_root), enable_file_watching=False, load_libraries=False
    )

    yield injector

    # Cleanup if needed
    # (registries are fresh per test, so no cleanup required)


@pytest.fixture(scope="function")
def test_injector_with_undo(project_root: Path) -> Generator[Injector, None, None]:
    """
    Provide test injector (kept for backwards-compat; undo is now per-graph).
    """
    injector = create_test_injector(
        workspace_root=str(project_root),
        enable_file_watching=False,
        load_libraries=False,
    )

    yield injector


@pytest.fixture(scope="session")
def library_system(project_root: Path, test_library_path: Path):
    """
    Provide fully initialized library system for integration tests.

    This is expensive, so it's session-scoped and shared across tests.
    Mark tests using this with @pytest.mark.integration
    """
    # Import here to avoid circular imports at module level
    from haywire.core.di.config import set_library_system, set_global_injector

    service = create_test_library_system(
        workspace_root=str(project_root),
        library_paths=[str(test_library_path)],
        load_libraries=True,
        enable_file_watching=False,
    )

    # IMPORTANT: Set global library system for graph operations
    set_library_system(service)
    set_global_injector(service.injector)

    yield service

    # Cleanup
    # Stop file watchers if any
    lib_registry = service.get_library_registry()
    if hasattr(lib_registry, "stop_file_watching"):
        lib_registry.stop_file_watching()

    # Clear global references
    set_library_system(None)
    set_global_injector(None)


# ==============================================================================
# Registry Fixtures (from DI)
# ==============================================================================


@pytest.fixture
def node_registry(test_injector: Injector) -> NodeRegistry:
    """Get node registry from DI."""
    return test_injector.get(NodeRegistry)


@pytest.fixture
def adapter_registry(test_injector: Injector) -> AdapterRegistry:
    """Get adapter registry from DI."""
    return test_injector.get(AdapterRegistry)


@pytest.fixture
def type_registry(test_injector: Injector) -> TypeRegistry:
    """Get type registry from DI."""
    return test_injector.get(TypeRegistry)


# ==============================================================================
# Factory Fixtures (from DI)
# ==============================================================================


@pytest.fixture
def node_factory(test_injector: Injector) -> NodeFactory:
    """Get node factory from DI."""
    return test_injector.get(NodeFactory)


@pytest.fixture
def adapter_factory(test_injector: Injector) -> AdapterFactory:
    """Get adapter factory from DI."""
    return test_injector.get(AdapterFactory)


# ==============================================================================
# Service Fixtures (from DI)
# ==============================================================================


@pytest.fixture
def history_manager() -> IHistoryManager:
    """Provide a fresh per-graph HistoryManager (no longer from DI)."""
    return HistoryManager(UndoConfig(max_actions=50))


# ==============================================================================
# Integration Test Fixtures
# ==============================================================================


@pytest.fixture
def integration_node_registry(library_system) -> NodeRegistry:
    """Get node registry with all libraries loaded."""
    return library_system.get_node_registry()


@pytest.fixture
def integration_node_factory(library_system) -> NodeFactory:
    """Get node factory with all libraries loaded."""
    return library_system.get_node_factory()


# ==============================================================================
# EditState Fixture (v1.2 — see internals/prd/v1.2-edit-state-migration.md)
# ==============================================================================


_EDIT_STATE_MODULE = "haybale_graph_editor.state.edit_state"


def attach_stub_session(instance):
    """Stamp a MagicMock as ``instance.session`` so ``signal_field`` writes
    on SessionState don't crash on the weakref deref.

    ``SessionState._signal_emit`` calls ``self.session()``; production code
    stamps a real ``weakref.ref(session)`` via
    ``LibraryStateContainer.attach_session_with_ref``. Tests that build a
    SessionState directly (without going through SessionManager) need
    this stub. The MagicMock is callable, and the value it returns has a
    callable ``.publish`` that harmlessly swallows the signal.
    """
    from unittest.mock import MagicMock

    instance.session = MagicMock()
    return instance


# ==============================================================================
# Promotion Fixtures (promote-setting-to-inlet — Plan 3)
# ==============================================================================


def _make_stub_node_wrapper(node_id: str):
    """A minimal NodeWrapper stand-in. ``NodeData.add``/``_pop`` call
    ``mark_as_structuraly_dirty``/``redraw`` on the wrapper."""
    return type(
        "W",
        (),
        {
            "node_id": node_id,
            "notify": lambda *a, **k: None,
            "mark_as_structuraly_dirty": lambda *a, **k: None,
            "redraw": lambda *a, **k: None,
        },
    )()


@pytest.fixture
def make_node_with_setting(library_system):
    """Build a live node with a plain ``setting[FLOAT]`` field (promotable).

    Signature: ``make_node_with_setting(accessor="filter", field="threshold",
    with_watch=False)`` → a ``NodeData`` instance whose ``<accessor>.<field>`` is a plain
    setting defaulting to 0.5. With ``with_watch=True`` the bag also carries a
    ``watch()`` field (``<field>_watched``) so menu tests can assert non-plain fields are
    filtered out of the promote submenu.

    Depends on ``library_system`` so the builtin types (``builtin:type:FLOAT``) are
    registered for ``DataPort.from_spec``.
    """
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.di.context import set_settings_registry, set_type_registry
    from haywire.core.node import BaseNode, node
    from haywire.core.settings import NodeSettings, setting, watch

    def _factory(accessor: str = "filter", field: str = "threshold", with_watch: bool = False):
        # Re-assert the loaded registries as the ambient context: a function-scoped
        # test_injector elsewhere in the suite can have swapped the module globals,
        # leaving the node to cache a registry without the builtin types.
        set_type_registry(library_system.get_type_registry())
        set_settings_registry(library_system.get_settings_registry())

        plain = setting[FLOAT](0.5)
        body: dict = {field: plain}
        if with_watch:
            # watch() mirrors *plain*; pass type_ explicitly because plain's generic
            # arg isn't resolved until its own __set_name__ runs (after this call).
            body[f"{field}_watched"] = watch(plain, type_=FLOAT)
        bag_cls = type(accessor, (NodeSettings,), body)
        node_cls = node(label="Promotion Test Node")(
            type("_PromotionTestNode", (BaseNode,), {accessor: bag_cls})
        )
        return node_cls("n1", _make_stub_node_wrapper("w1"))

    return _factory


@pytest.fixture
def register_edit_state() -> Callable[[LibraryStateContainer, str], type]:
    """Register EditState into a LibraryStateContainer for tests.

    Returns a helper that takes a container and a session id, registers
    EditState as a session-scoped class, and attaches the session so
    ``container.get_session(EditState, sid)`` returns an instance
    immediately. See ``attach_stub_session`` for why ``.session`` is
    stamped.
    """

    def _register(container: LibraryStateContainer, session_id: str) -> type:
        edit_state_cls = importlib.import_module(_EDIT_STATE_MODULE).EditState
        container._add_session_class(edit_state_cls, edit_state_cls.class_identity.registry_key)
        container.attach_session(session_id)
        attach_stub_session(container.get_session(edit_state_cls, session_id))
        return edit_state_cls

    return _register
