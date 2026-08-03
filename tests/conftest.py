"""
Root pytest configuration with DI fixtures.

Provides fixtures for different test scopes and scenarios.
"""

import importlib
from pathlib import Path
from typing import Any, Callable, Generator, TYPE_CHECKING

import pytest
from injector import Injector

from haywire.core.di.test_config import create_test_injector, create_test_library_system

from haywire.core.node.registry import NodeRegistry
from haywire.core.node.factory import NodeFactory
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.adapter.factory import AdapterFactory
from haywire.core.types.registry import TypeRegistry
from haywire.core.state import LibraryStateContainer
from haywire.core.undo.interfaces import IHistoryManager
from haywire.core.undo.history_manager import HistoryManager
from haywire.core.undo.config import UndoConfig

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.node_wrapper import NodeWrapper


# ==============================================================================
# Pytest Configuration
# ==============================================================================


class _BrowserTestsLast:
    """Force Playwright browser tests to run after everything else.

    pytest-playwright's sync API parks a *running* asyncio event loop in the
    main thread (greenlet-based) for the rest of the session once the first
    browser test runs. Any anyio/asyncio test that runs after it in the same
    process then fails with "Cannot run the event loop while another loop is
    running" / "Runner is closed". Alphabetical collection happened to run the
    async tests first; this hook turns that accident into an invariant so the
    suite stays green under any collection order (subset runs, reordering
    plugins, future test files that sort after tests/ui/harness/).

    Registered as a separate plugin object so this trylast sort and the
    tryfirst marker application below can both hook
    ``pytest_collection_modifyitems``.
    """

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items):
        non_browser = [i for i in items if "browser" not in i.keywords]
        browser = [i for i in items if "browser" in i.keywords]
        items[:] = non_browser + browser


def pytest_configure(config):
    """Register custom markers and the browser-last ordering plugin."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (slower, full system)")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "ui: UI-related tests")
    config.addinivalue_line("markers", "core: Core functionality tests")
    config.addinivalue_line(
        "markers",
        "browser: Playwright browser tests (auto-applied to tests/ui/harness/; always run last)",
    )
    config.pluginmanager.register(_BrowserTestsLast(), "browser-tests-last")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    """Auto-apply the ``browser`` marker to everything under tests/ui/harness/.

    tryfirst so the marker exists before pytest's own ``-m`` deselection
    filters on it — ``-m "not browser and not perf"`` gives a browser-free
    fast run. Playwright tests added outside tests/ui/harness/ must carry
    ``@pytest.mark.browser`` themselves. The browser-last SORT lives in
    ``_BrowserTestsLast`` (trylast) so it runs after any deselection or
    reordering.
    """
    browser_marker = pytest.mark.browser
    for item in items:
        if item.nodeid.startswith("tests/ui/harness/"):
            item.add_marker(browser_marker)


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
# Cached venv metadata scan for dep-detection tests
# ==============================================================================


@pytest.fixture(scope="module")
def cached_packages_distributions():
    """Memoize ``importlib.metadata.packages_distributions()`` for one test module.

    Building the module→distribution mapping scans every installed dist's
    metadata (~1s in this venv), and ``detect_deps`` fetches it once per run.
    Tests that call detect/drift code many times (test_dep_detect,
    test_share_drift) re-pay that scan per test for an identical result — the
    venv cannot change mid-run. Opt in per module with
    ``pytestmark = pytest.mark.usefixtures("cached_packages_distributions")``.
    Do NOT use in tests that install or remove distributions.
    """
    import importlib.metadata

    mapping = importlib.metadata.packages_distributions()
    mp = pytest.MonkeyPatch()
    mp.setattr(importlib.metadata, "packages_distributions", lambda: mapping)
    yield mapping
    mp.undo()


# ==============================================================================
# Ambient settings registry for DI-less tests
# ==============================================================================
# Since ADR 0022, ``BaseGraph.__init__`` reads ``get_settings_registry()`` from
# the ambient DI context (module-level globals in haywire.core.di.context — NOT
# ContextVar, so they persist across tests). DI-less unit tests that construct a
# bare ``BaseGraph()`` therefore need *some* ambient ``SettingsRegistry``, or they
# raise "SettingsRegistry not set in ambient context". Previously they only passed
# by accident, piggybacking on a registry an earlier integration test had leaked
# into the globals — so the same test failed when run in isolation.
#
# This autouse fixture makes DI-less tests deterministic without corrupting the
# session-scoped integration registry.
#
# The subtlety: constructing a ``SettingsRegistry()`` is NOT side-effect-free. Its
# ``__init__`` calls ``_drain_pending_global()``, which repoints the class-level
# ``FrameworkSettings._registry`` at itself and *drains* the module-level
# ``_pending_global`` queue of framework schema classes. A naive throwaway registry
# would therefore hijack where later-defined FrameworkSettings register and empty a
# queue the real session registry still needs — which is exactly how a bare fallback
# made ``ui.node.default.skin.studio_skin`` vanish from the session registry.
#
# So we snapshot ALL THREE pieces of global state a fallback would touch
# (``di_context._settings_registry``, ``FrameworkSettings._registry``, and the
# ``_pending_global`` list contents) and restore them verbatim on teardown, leaving
# a DI-less test's fallback fully contained. When nothing is set, we install a
# minimal registry so bare ``BaseGraph()`` construction works.
#
# The session library-system registry (set once via ``provide_settings_registry``)
# is not re-run per test, so integration graph fixtures re-assert it themselves at
# use time (see ``graph_with_library_system``).
@pytest.fixture(autouse=True)
def _ambient_settings_registry():
    from haywire.core.di import context as di_context
    from haywire.core.settings import settings_framework as fw
    from haywire.core.settings.registry import SettingsRegistry

    prev_ambient = di_context._settings_registry
    prev_fw_registry = fw.FrameworkSettings._registry
    prev_pending = list(fw._pending_global)

    if prev_ambient is None:
        # Constructing this drains _pending_global and repoints
        # FrameworkSettings._registry — both restored below.
        di_context.set_settings_registry(SettingsRegistry())

    try:
        yield
    finally:
        di_context._settings_registry = prev_ambient
        fw.FrameworkSettings._registry = prev_fw_registry
        fw._pending_global[:] = prev_pending


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

# Every ambient DI module-global a function-scoped injector's providers can
# repoint via their set_*() calls (haywire.core.di.context) plus the global
# injector/library-system pair (haywire.core.di.config).
_DI_CONTEXT_GLOBALS = (
    "_node_factory",
    "_adapter_factory",
    "_type_registry",
    "_settings_registry",
    "_session_manager",
    "_workspace_root",
    "_library_state_container",
    "_error_ledger",
)
_DI_CONFIG_GLOBALS = ("_global_injector", "_global_library_system")


def _snapshot_ambient_di() -> dict:
    from haywire.core.di import config as di_config
    from haywire.core.di import context as di_context

    snap = {("context", n): getattr(di_context, n) for n in _DI_CONTEXT_GLOBALS}
    snap.update({("config", n): getattr(di_config, n) for n in _DI_CONFIG_GLOBALS})
    return snap


def _restore_ambient_di(snap: dict) -> None:
    from haywire.core.di import config as di_config
    from haywire.core.di import context as di_context

    modules = {"context": di_context, "config": di_config}
    for (mod, name), value in snap.items():
        setattr(modules[mod], name, value)


@pytest.fixture
def test_injector(project_root: Path) -> Generator[Injector, None, None]:
    """
    Provide a fresh test injector for each test.

    This is for unit tests that need DI but not full library loading.

    The injector's providers repoint the ambient DI globals (set_type_registry
    etc.) lazily on first ``injector.get(...)`` — without restore, a unit test
    using this fixture leaves the ambient context pointing at its fresh,
    library-less registries, and any later test that reads the ambient context
    (node init resolving ``core:type:CALLBACK``, for example) fails depending
    on execution order. Snapshot/restore keeps the poisoning contained.
    """
    snap = _snapshot_ambient_di()
    injector = create_test_injector(
        workspace_root=str(project_root), enable_file_watching=False, load_libraries=False
    )

    yield injector

    _restore_ambient_di(snap)


@pytest.fixture
def test_injector_with_undo(project_root: Path) -> Generator[Injector, None, None]:
    """
    Provide test injector (kept for backwards-compat; undo is now per-graph).

    Same ambient-DI snapshot/restore as ``test_injector`` — see there.
    """
    snap = _snapshot_ambient_di()
    injector = create_test_injector(
        workspace_root=str(project_root),
        enable_file_watching=False,
        load_libraries=False,
    )

    yield injector

    _restore_ambient_di(snap)


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
    with_watch=False)`` -> a ``NodeData`` instance whose ``<accessor>.<field>`` is a plain
    setting defaulting to 0.5. With ``with_watch=True`` the bag also carries a
    ``watch()`` field (``<field>_watched``) mirroring
    ``TestingSettings.default_intensity`` (a real cross-bag LibrarySettings
    global, forced to 0.5 here) — same-bag mirroring is no longer supported
    (mirrors= must reference a field on a different class).

    Depends on ``library_system`` so the builtin types (``builtin:type:FLOAT``) are
    registered for ``DataPort.from_spec``.
    """
    from haybale_testing.settings.testing import TestingSettings
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
            registry = library_system.get_settings_registry()
            registry.set_global(TestingSettings.default_intensity._setting_key, 0.5)
            body[f"{field}_watched"] = watch(TestingSettings.default_intensity, type_=FLOAT)
        bag_cls = type(accessor, (NodeSettings,), body)
        node_cls: type = node(label="Promotion Test Node")(
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


# ==============================================================================
# Graph construction helpers
# ==============================================================================


def make_node(graph: "BaseGraph", registry_key: str, **kwargs: Any) -> "NodeWrapper":
    """``graph.create_node_wrapper`` narrowed to a non-Optional NodeWrapper.

    The factory is Optional-returning, but tests overwhelmingly treat a failed
    creation as a broken precondition rather than a case under test. Narrowing
    here keeps the failure loud (and typed) instead of surfacing later as an
    ``AttributeError`` on None.
    """
    wrapper = graph.create_node_wrapper(registry_key, **kwargs)
    assert wrapper is not None, f"node creation failed for {registry_key!r}"
    return wrapper


def make_edge(
    graph: "BaseGraph",
    source_node_id: str,
    outlet_port_id: str,
    sink_node_id: str,
    inlet_port_id: str,
    **kwargs: Any,
) -> "EdgeWrapper":
    """``graph.create_edge_wrapper`` narrowed to a non-Optional EdgeWrapper.

    A None here means the graph refused to build an edge at all — distinct from
    building an *invalid* edge, which tests assert on via ``edge.state``.
    """
    edge = graph.create_edge_wrapper(source_node_id, outlet_port_id, sink_node_id, inlet_port_id, **kwargs)
    assert edge is not None, f"edge creation failed: {outlet_port_id} -> {inlet_port_id}"
    return edge
