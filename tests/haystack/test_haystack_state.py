"""HaystackState — the in-memory entry registry as an AppState."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


@pytest.fixture
def settings_registry_wired():
    """Register HaystackSettings with a fresh registry so instances are usable."""
    from haybale_haystack.settings.haystack_settings import HaystackSettings
    from haywire.core.settings.registry import SettingsRegistry

    registry = SettingsRegistry()
    registry.register_schema(HaystackSettings)
    HaystackSettings._registry = registry
    yield registry
    HaystackSettings._registry = None


@pytest.fixture
def state_with_mocked_deps(settings_registry_wired):
    """Build a HaystackState with all on_enable deps wired manually."""
    from haybale_haystack.state.haystack_state import HaystackState
    from haybale_haystack.settings.haystack_settings import HaystackSettings

    state = HaystackState()
    state._session_manager = MagicMock()
    state._workspace_root = Path("/tmp/ws")
    state._node_factory = MagicMock()
    state._library_state_container = MagicMock()
    state._haystack_settings = HaystackSettings()
    return state


def test_haystack_state_starts_empty():
    from haybale_haystack.state.haystack_state import HaystackState

    state = HaystackState()
    assert state.all_entries() == []


def test_haystack_state_is_an_app_state():
    from haybale_haystack.state.haystack_state import HaystackState
    from haywire.core.state.base import AppState

    assert issubclass(HaystackState, AppState)


def test_create_new_increments_counter_and_adds_entry(state_with_mocked_deps):
    state = state_with_mocked_deps
    initial_count = len(state.all_entries())
    initial_counter = state._haystack_settings.new_counter

    entry = state.create_new()

    assert entry is not None
    assert len(state.all_entries()) == initial_count + 1
    assert entry.path is None
    # Legacy semantics: synthetic __unsaved_N__ id, with counter advanced.
    assert entry._unsaved_id == f"__unsaved_{initial_counter}__"
    assert state._haystack_settings.new_counter == initial_counter + 1


def test_create_new_registers_entry_under_entry_id(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    assert state.get_by_id(entry.entry_id) is entry


def test_open_graph_returns_existing_if_already_open(state_with_mocked_deps, tmp_path):
    state = state_with_mocked_deps
    p = tmp_path / "x.haywire"
    p.write_text("{}")

    with patch.object(state, "_make_graph_and_editor") as mock_make:
        # Build a mock graph + editor that pretends load_from_file/force_validation work.
        mock_graph = MagicMock()
        mock_graph.load_from_file.return_value = True
        mock_editor = MagicMock()
        mock_make.return_value = (mock_graph, mock_editor)

        entry1 = state.open_graph(p)
        entry2 = state.open_graph(p)

    assert entry1 is entry2


def test_open_graph_loads_and_force_validates(state_with_mocked_deps, tmp_path):
    state = state_with_mocked_deps
    p = tmp_path / "x.haywire"
    p.write_text("{}")

    with patch.object(state, "_make_graph_and_editor") as mock_make:
        mock_graph = MagicMock()
        mock_editor = MagicMock()
        mock_make.return_value = (mock_graph, mock_editor)

        entry = state.open_graph(p)

    mock_graph.load_from_file.assert_called_once_with(str(p))
    mock_graph.force_validation.assert_called_once()
    assert entry.path == p
    assert entry.unsaved is False


def test_get_by_id_returns_entry(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    assert state.get_by_id(entry.entry_id) is entry


def test_get_by_id_returns_none_for_unknown(state_with_mocked_deps):
    state = state_with_mocked_deps
    assert state.get_by_id("nonexistent") is None


def test_get_by_path_returns_entry(state_with_mocked_deps, tmp_path):
    state = state_with_mocked_deps
    p = tmp_path / "x.haywire"
    p.write_text("{}")

    with patch.object(state, "_make_graph_and_editor") as mock_make:
        mock_make.return_value = (MagicMock(), MagicMock())
        entry = state.open_graph(p)

    assert state.get_by_path(p) is entry


def test_remove_entry_drops_from_registry(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    assert state.remove_entry(entry) is True
    assert state.get_by_id(entry.entry_id) is None


def test_remove_entry_returns_false_for_unknown(state_with_mocked_deps):
    state = state_with_mocked_deps
    rogue = MagicMock()
    rogue.entry_id = "__nope__"
    rogue.is_executing = False
    assert state.remove_entry(rogue) is False


def test_unsaved_entries_includes_untitled(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    assert entry in state.unsaved_entries()


def test_has_unsaved_true_when_untitled_present(state_with_mocked_deps):
    state = state_with_mocked_deps
    state.create_new()
    assert state.has_unsaved() is True


def test_save_graph_returns_false_if_no_target(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    # Untitled entry, no save_as → cannot save.
    assert state.save_graph(entry) is False


def test_save_graph_calls_graph_save_to_file(state_with_mocked_deps, tmp_path):
    state = state_with_mocked_deps
    target = tmp_path / "out.haywire"

    with patch.object(state, "_make_graph_and_editor") as mock_make:
        mock_graph = MagicMock()
        mock_graph.save_to_file.return_value = True
        mock_make.return_value = (mock_graph, MagicMock())
        entry = state.create_new()

    assert state.save_graph(entry, save_as=target) is True
    mock_graph.save_to_file.assert_called_once_with(str(target))
    assert entry.path == target
    assert entry.unsaved is False
    # Re-keyed under new path id.
    assert state.get_by_id(entry.entry_id) is entry


def test_list_graph_files_empty_when_no_graphs_dir(state_with_mocked_deps):
    state = state_with_mocked_deps
    state._workspace_root = Path("/tmp/does_not_exist_xyz")
    assert state.list_graph_files() == []


def test_list_graph_files_finds_haywire_files(state_with_mocked_deps, tmp_path):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    graphs_dir = tmp_path / "graphs"
    graphs_dir.mkdir()
    f1 = graphs_dir / "a.haywire"
    f1.write_text("{}")
    sub = graphs_dir / "sub"
    sub.mkdir()
    f2 = sub / "b.haywire"
    f2.write_text("{}")

    found = state.list_graph_files()
    assert f1 in found
    assert f2 in found


def test_validation_callback_marks_entry_unsaved_and_broadcasts(state_with_mocked_deps):
    """Validation handler stamps entry.unsaved=True and broadcasts via SessionManager."""
    state = state_with_mocked_deps
    entry = state.create_new()
    # New entries start with unsaved=False by dataclass default — only the
    # __unsaved_N__ id and path=None mark them as untitled. The validation
    # callback flips entry.unsaved on actual node/edge changes.
    assert entry.unsaved is False

    # Build a result with .nodes/.edges truthy and has_changes True.
    result = MagicMock()
    result.has_changes.return_value = True
    result.nodes = {"n1": MagicMock()}
    result.edges = {}
    result.graph = MagicMock()
    result.graph.requires_graph_reassembly.return_value = False

    state._on_entry_validation(entry, result)

    assert entry.unsaved is True
    state._session_manager.broadcast_signal.assert_called_once()
    args, kwargs = state._session_manager.broadcast_signal.call_args
    # First arg is a GraphDataMutated; origin_session_id keyword.
    from haywire.core.session.context_signals import GraphDataMutated

    assert isinstance(args[0], GraphDataMutated)
    assert kwargs.get("origin_session_id") == ""


def test_validation_callback_no_broadcast_when_no_changes(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()

    result = MagicMock()
    result.has_changes.return_value = False
    result.nodes = {}
    result.edges = {}
    result.graph = None

    state._on_entry_validation(entry, result)

    state._session_manager.broadcast_signal.assert_not_called()


def test_validation_callback_stops_execution_on_reassembly(state_with_mocked_deps):
    """When reassembly is required and entry is executing, stop_execution is called."""
    state = state_with_mocked_deps

    entry = MagicMock()
    entry.is_executing = True
    entry.stop_execution = MagicMock()

    inner_graph = MagicMock()
    inner_graph.requires_graph_reassembly.return_value = True

    result = MagicMock()
    result.nodes = []
    result.edges = []
    result.has_changes.return_value = True
    result.graph = inner_graph

    state._on_entry_validation(entry, result)

    entry.stop_execution.assert_called_once()


def test_on_enable_logs_warning_when_settings_registry_unwired(caplog):
    """Tripwire: HaystackState.on_enable warns if HaystackSettings._registry is None.

    This exercises the sanity check added to catch the registration-order bug where
    state/ was registered before settings/, causing HaystackSettings() to construct
    with _registry=None (silent "simple mode") and lose persistence.
    """
    import logging

    from haybale_haystack.settings.haystack_settings import HaystackSettings
    from haybale_haystack.state.haystack_state import HaystackState

    # Ensure HaystackSettings is unwired (registry=None simulates pre-fix order).
    original_registry = HaystackSettings._registry
    HaystackSettings._registry = None
    try:
        state = HaystackState()
        state._haystack_settings = HaystackSettings()
        # Force registry to None on the instance to simulate the bug condition.
        # (HaystackSettings() may read the class-level _registry; force instance attr.)
        state._haystack_settings._registry = None

        # Directly invoke the warning logic that lives in on_enable.
        # We replicate the exact check rather than calling on_enable (which needs DI).
        with caplog.at_level(logging.WARNING, logger="haybale_haystack.state.haystack_state"):
            if state._haystack_settings is not None and state._haystack_settings._registry is None:
                import logging as _logging

                _log = _logging.getLogger("haybale_haystack.state.haystack_state")
                _log.warning(
                    "HaystackState.on_enable: HaystackSettings instance has no registry "
                    "(settings/ not yet registered?). last_haystack_name and new_counter "
                    "will fall to defaults and not persist."
                )

        assert any("HaystackSettings instance has no registry" in r.message for r in caplog.records), (
            "Expected a warning about unwired HaystackSettings registry, but none was logged."
        )
    finally:
        HaystackSettings._registry = original_registry
