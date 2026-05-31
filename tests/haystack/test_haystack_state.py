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

    state = HaystackState()
    # AppState's _session_manager is a weakref dereffed via self._session_manager().
    # A mock returning itself lets the existing `_session_manager.broadcast`
    # assertions target the same object the code calls broadcast on.
    state._session_manager = MagicMock()
    state._session_manager.return_value = state._session_manager
    state._workspace_root = Path("/tmp/ws")
    state._node_factory = MagicMock()
    state._library_state_container = MagicMock()
    return state


def test_haystack_state_starts_empty(settings_registry_wired):
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


def test_create_new_broadcasts_graph_data_mutated(state_with_mocked_deps):
    """Every mutator broadcasts GraphDataMutated cross-session.

    Centralising this in HaystackState (rather than at every UI call
    site) ensures peer sessions always observe haystack changes — no
    matter which entry-point added the entry (HaystackEditor +,
    file-browser panel, persistence rehydration, future call sites).
    """
    from haywire.core.session.signals import GraphDataMutated

    state = state_with_mocked_deps
    state._session_manager.broadcast.reset_mock()

    state.create_new()

    state._session_manager.broadcast.assert_called_once()
    (event,), _ = state._session_manager.broadcast.call_args
    assert isinstance(event, GraphDataMutated)


def test_create_new_registers_entry_under_binding_id(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    assert state.get_by_id(entry.binding_id) is entry


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
    assert state.get_by_id(entry.binding_id) is entry


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
    assert state.get_by_id(entry.binding_id) is None


def test_remove_entry_returns_false_for_unknown(state_with_mocked_deps):
    state = state_with_mocked_deps
    rogue = MagicMock()
    rogue.binding_id = "__nope__"
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
    assert state.get_by_id(entry.binding_id) is entry


def test_save_as_rekeys_graph_app_state(state_with_mocked_deps, tmp_path):
    """save_graph(save_as=new_path) rekeys the entry in GraphAppState."""
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    state = state_with_mocked_deps

    # Hand-register a GraphAppState. In production HaystackState does this
    # automatically (Task 13); for THIS test we exercise rekey in isolation.
    gas = GraphAppState()
    state._graph_app_state = gas

    with patch.object(state, "_make_graph_and_editor") as mock_make:
        mock_graph = MagicMock()
        mock_graph.save_to_file.return_value = True
        mock_make.return_value = (mock_graph, MagicMock())
        entry = state.create_new()

    old_binding_id = entry.binding_id  # "__unsaved_1__" or similar
    gas.register(entry)

    new_path = tmp_path / "renamed.haywire"
    new_path.parent.mkdir(parents=True, exist_ok=True)

    success = state.save_graph(entry, save_as=new_path)
    assert success
    assert entry.binding_id == str(new_path)
    assert gas.get(old_binding_id) is None
    assert gas.get(entry.binding_id) is entry


def test_create_new_registers_in_graph_app_state(state_with_mocked_deps):
    """create_new() registers the new entry in GraphAppState."""
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    state = state_with_mocked_deps
    gas = GraphAppState()
    state._graph_app_state = gas

    with patch.object(state, "_make_graph_and_editor") as mock_make:
        mock_make.return_value = (MagicMock(), MagicMock())
        entry = state.create_new()

    assert gas.get(entry.binding_id) is entry


def test_open_graph_registers_in_graph_app_state(state_with_mocked_deps, tmp_path):
    """open_graph() registers the loaded entry in GraphAppState."""
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    state = state_with_mocked_deps
    gas = GraphAppState()
    state._graph_app_state = gas

    graph_path = tmp_path / "graphs" / "g.haywire"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text("")

    mock_graph = MagicMock()
    mock_graph.load_from_file = MagicMock(return_value=None)
    mock_graph.force_validation = MagicMock(return_value=None)
    mock_editor = MagicMock()

    with patch.object(state, "_make_graph_and_editor", return_value=(mock_graph, mock_editor)):
        entry = state.open_graph(graph_path)

    assert gas.get(entry.binding_id) is entry


def test_remove_entry_unregisters_from_graph_app_state(state_with_mocked_deps):
    """remove_entry() unregisters the entry from GraphAppState."""
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    state = state_with_mocked_deps
    gas = GraphAppState()
    state._graph_app_state = gas

    with patch.object(state, "_make_graph_and_editor") as mock_make:
        mock_make.return_value = (MagicMock(), MagicMock())
        entry = state.create_new()
    bid = entry.binding_id
    assert gas.get(bid) is entry

    state.remove_entry(entry)
    assert gas.get(bid) is None


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
    # create_new() itself broadcasts (every mutator does). Reset so this
    # test only observes what _on_entry_validation broadcasts.
    state._session_manager.broadcast.reset_mock()

    # Build a result with .nodes/.edges truthy and has_changes True.
    result = MagicMock()
    result.has_changes.return_value = True
    result.nodes = {"n1": MagicMock()}
    result.edges = {}
    result.graph = MagicMock()
    result.graph.requires_graph_reassembly.return_value = False

    state._on_entry_validation(entry, result)

    assert entry.unsaved is True
    state._session_manager.broadcast.assert_called_once()
    (event,), _ = state._session_manager.broadcast.call_args
    from haywire.core.session.signals import GraphDataMutated

    assert isinstance(event, GraphDataMutated)


def test_validation_callback_no_broadcast_when_no_changes(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    # create_new() now broadcasts GraphDataMutated itself (every mutator
    # does). Reset the mock so this test only observes what
    # _on_entry_validation does with no-change results.
    state._session_manager.broadcast.reset_mock()

    result = MagicMock()
    result.has_changes.return_value = False
    result.nodes = {}
    result.edges = {}
    result.graph = None

    state._on_entry_validation(entry, result)

    state._session_manager.broadcast.assert_not_called()


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


def test_save_haystack_calls_persistence_and_updates_last_name(
    state_with_mocked_deps, tmp_path, monkeypatch
):
    """save_haystack delegates to persistence.dump_haystack and records the name in settings."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path

    dumped = {}

    def fake_dump(s, root, name, active_path=None):
        dumped["name"] = name
        dumped["root"] = root
        dumped["active_path"] = active_path
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)

    active = tmp_path / "graphs" / "foo.haywire"
    result = state.save_haystack("session1", active_path=active)

    assert dumped == {"name": "session1", "root": tmp_path, "active_path": active}
    assert state._haystack_settings.last_haystack_name == "session1"
    assert result == tmp_path / "haystacks" / "session1.toml"


def test_save_haystack_without_active_path(state_with_mocked_deps, tmp_path, monkeypatch):
    """active_path is optional; default None propagates through."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path

    captured = {}

    def fake_dump(s, root, name, active_path=None):
        captured["active_path"] = active_path
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)

    result = state.save_haystack("session1")
    assert captured["active_path"] is None
    assert state._haystack_settings.last_haystack_name == "session1"
    assert result == tmp_path / "haystacks" / "session1.toml"


def test_load_haystack_calls_persistence_and_updates_last_name(
    state_with_mocked_deps, tmp_path, monkeypatch
):
    """load_haystack delegates to persistence.load_haystack and records the name in settings."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path

    # Create the TOML file so source.exists() returns True (required for last_haystack_name
    # to be updated — the guard was added to prevent poisoning on missing-file loads).
    haystacks_dir = tmp_path / "haystacks"
    haystacks_dir.mkdir()
    (haystacks_dir / "session1.toml").write_text("")

    expected_active = tmp_path / "graphs" / "foo.haywire"

    def fake_load(s, root, name):
        return expected_active

    monkeypatch.setattr("haybale_haystack.persistence.load_haystack", fake_load)

    result = state.load_haystack("session1")

    assert result == expected_active
    assert state._haystack_settings.last_haystack_name == "session1"


def test_load_haystack_missing_file_does_not_update_last_name(state_with_mocked_deps, tmp_path):
    """If the named haystack TOML does not exist, last_haystack_name must NOT
    be updated — otherwise the next on_enable would try to rehydrate from a
    file that doesn't exist."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.last_haystack_name = "previous"

    # No haystacks/ directory created — file is missing.
    result = state.load_haystack("nonexistent")

    assert result is None
    assert state._haystack_settings.last_haystack_name == "previous"


def test_start_execution_calls_entry_method(state_with_mocked_deps):
    """HaystackState.start_execution forwards to entry.start_execution."""
    state = state_with_mocked_deps
    entry = MagicMock()

    state.start_execution(entry)

    entry.start_execution.assert_called_once_with()


def test_stop_execution_calls_entry_method(state_with_mocked_deps):
    """HaystackState.stop_execution forwards to entry.stop_execution."""
    state = state_with_mocked_deps
    entry = MagicMock()

    state.stop_execution(entry)

    entry.stop_execution.assert_called_once_with()


# ---------------------------------------------------------------------------
# HaystackState._haystack_dirty flag
# ---------------------------------------------------------------------------


def test_haystack_dirty_starts_false(state_with_mocked_deps):
    assert state_with_mocked_deps._haystack_dirty is False


def test_create_new_marks_haystack_dirty(state_with_mocked_deps):
    state = state_with_mocked_deps
    state.create_new()
    assert state._haystack_dirty is True


def test_save_haystack_clears_dirty(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state.create_new()
    assert state._haystack_dirty is True

    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda s, root, name, active_path=None: root / "haystacks" / f"{name}.toml",
    )
    state.save_haystack("session1")
    assert state._haystack_dirty is False


def test_load_haystack_clears_dirty(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_dirty = True  # pretend we had pending changes

    # persistence.load_haystack returns None for missing file; we still
    # expect the dirty flag to clear because we set last_name to a known
    # value via the load path.
    haystacks_dir = tmp_path / "haystacks"
    haystacks_dir.mkdir()
    (haystacks_dir / "session1.toml").write_text('[haystack]\nname = "session1"\n')
    state.load_haystack("session1")
    assert state._haystack_dirty is False


def test_open_graph_marks_haystack_dirty(state_with_mocked_deps, tmp_path):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    p = tmp_path / "graphs" / "foo.haywire"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    from unittest.mock import patch

    with (
        patch("haywire.core.graph.base.BaseGraph.load_from_file"),
        patch("haywire.core.graph.base.BaseGraph.force_validation"),
    ):
        state.open_graph(p)
    assert state._haystack_dirty is True


def test_remove_entry_marks_haystack_dirty(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    entry = state.create_new()
    # Clear dirty so we know remove_entry sets it again.
    state._haystack_dirty = False
    state.remove_entry(entry)
    assert state._haystack_dirty is True


def test_rename_graph_marks_haystack_dirty(state_with_mocked_deps, tmp_path):
    from unittest.mock import MagicMock

    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    p = tmp_path / "graphs" / "foo.haywire"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    entry = MagicMock()
    entry.path = p
    entry.binding_id = str(p)
    state._entries[entry.binding_id] = entry
    state._haystack_dirty = False
    state.rename_graph(entry, "bar")
    assert state._haystack_dirty is True


def test_save_graph_marks_haystack_dirty(state_with_mocked_deps, tmp_path):
    from unittest.mock import MagicMock

    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    entry = state.create_new()
    entry.graph = MagicMock()
    entry.graph.save_to_file.return_value = True
    state._haystack_dirty = False
    state.save_graph(entry, save_as=tmp_path / "graphs" / "foo.haywire")
    assert state._haystack_dirty is True


def test_start_execution_marks_haystack_dirty(state_with_mocked_deps):
    from unittest.mock import MagicMock

    state = state_with_mocked_deps
    state._haystack_dirty = False
    state.start_execution(MagicMock())
    assert state._haystack_dirty is True


def test_stop_execution_marks_haystack_dirty(state_with_mocked_deps):
    from unittest.mock import MagicMock

    state = state_with_mocked_deps
    state._haystack_dirty = False
    state.stop_execution(MagicMock())
    assert state._haystack_dirty is True
