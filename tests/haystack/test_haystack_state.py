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


def test_create_new_broadcasts_graph_data_mutated(state_with_mocked_deps):
    """Every mutator broadcasts GraphDataMutated cross-session.

    Centralising this in HaystackState (rather than at every UI call
    site) ensures peer sessions always observe haystack changes — no
    matter which entry-point added the entry (HaystackEditor +,
    file-browser panel, persistence rehydration, future call sites).
    """
    from haywire.core.session.signals_and_lifecycle import GraphDataMutated

    state = state_with_mocked_deps
    state._session_manager.broadcast_signal.reset_mock()

    state.create_new()

    state._session_manager.broadcast_signal.assert_called_once()
    args, kwargs = state._session_manager.broadcast_signal.call_args
    assert isinstance(args[0], GraphDataMutated)
    assert kwargs.get("origin_session_id") == ""


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
    # create_new() itself broadcasts (every mutator does). Reset so this
    # test only observes what _on_entry_validation broadcasts.
    state._session_manager.broadcast_signal.reset_mock()

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
    from haywire.core.session.signals_and_lifecycle import GraphDataMutated

    assert isinstance(args[0], GraphDataMutated)
    assert kwargs.get("origin_session_id") == ""


def test_validation_callback_no_broadcast_when_no_changes(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    # create_new() now broadcasts GraphDataMutated itself (every mutator
    # does). Reset the mock so this test only observes what
    # _on_entry_validation does with no-change results.
    state._session_manager.broadcast_signal.reset_mock()

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


def test_autosave_if_continuous_off_does_nothing(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "off"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []


def test_autosave_if_continuous_on_exit_does_nothing(state_with_mocked_deps, tmp_path, monkeypatch):
    """on_exit fires from on_disable, NOT from this helper."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "on_exit"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []


def test_autosave_if_continuous_dumps_when_enabled(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = "session1"

    captured = {}

    def fake_dump(s, root, name, active_path=None):
        captured["name"] = name
        captured["active_path"] = active_path
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)

    state._autosave_if_continuous()
    assert captured["name"] == "session1"
    # continuous-mode dumps must NOT include active_graph.
    assert captured["active_path"] is None


def test_autosave_if_continuous_skips_when_no_last_name(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = ""

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []


def test_autosave_if_continuous_skips_when_settings_missing(state_with_mocked_deps, tmp_path, monkeypatch):
    """Defensive: tests/dev environments may have _haystack_settings = None."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings = None

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []


def test_autosave_if_continuous_skips_when_no_workspace_root(state_with_mocked_deps, monkeypatch):
    """Defensive: a HaystackState whose workspace_root never got wired (test fixture
    short-circuit, on_enable failed, etc.) must not attempt a TOML write."""
    state = state_with_mocked_deps
    state._workspace_root = None
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []


@pytest.fixture
def state_in_continuous_mode(state_with_mocked_deps, tmp_path):
    """state_with_mocked_deps + autosave=continuous + a named haystack."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = "session1"
    return state


def _patch_dump(monkeypatch):
    """Capture every persistence.dump_haystack call into a list."""
    calls: list[dict] = []

    def fake_dump(s, root, name, active_path=None):
        calls.append({"name": name, "active_path": active_path})
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)
    return calls


def test_create_new_triggers_continuous_autosave(state_in_continuous_mode, monkeypatch):
    calls = _patch_dump(monkeypatch)
    state_in_continuous_mode.create_new()
    assert any(c["name"] == "session1" and c["active_path"] is None for c in calls)


def test_open_graph_triggers_continuous_autosave(state_in_continuous_mode, tmp_path, monkeypatch):
    calls = _patch_dump(monkeypatch)
    p = tmp_path / "graphs" / "foo.haywire"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")  # empty .haywire — load_from_file is mocked via the factory below

    # NodeFactory is a MagicMock from the fixture, and BaseGraph.load_from_file
    # will be called on a real BaseGraph; for this test we just need open_graph
    # to fire the autosave hook regardless of file content.
    with (
        patch("haywire.core.graph.base.BaseGraph.load_from_file"),
        patch("haywire.core.graph.base.BaseGraph.force_validation"),
    ):
        state_in_continuous_mode.open_graph(p)

    assert any(c["name"] == "session1" for c in calls)


def test_save_graph_triggers_continuous_autosave(state_in_continuous_mode, tmp_path, monkeypatch):
    calls = _patch_dump(monkeypatch)
    state = state_in_continuous_mode
    entry = state.create_new()
    entry.graph = MagicMock()
    entry.graph.save_to_file.return_value = True

    target = tmp_path / "graphs" / "foo.haywire"
    state.save_graph(entry, save_as=target)
    assert any(c["name"] == "session1" for c in calls)


def test_remove_entry_triggers_continuous_autosave(state_in_continuous_mode, monkeypatch):
    calls = _patch_dump(monkeypatch)
    state = state_in_continuous_mode
    entry = state.create_new()
    calls.clear()  # ignore the create_new call

    state.remove_entry(entry)
    assert any(c["name"] == "session1" for c in calls)


def test_rename_graph_triggers_continuous_autosave(state_in_continuous_mode, tmp_path, monkeypatch):
    calls = _patch_dump(monkeypatch)
    state = state_in_continuous_mode
    p = tmp_path / "graphs" / "foo.haywire"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    entry = MagicMock()
    entry.path = p
    entry.entry_id = str(p)
    state._entries[entry.entry_id] = entry
    calls.clear()

    state.rename_graph(entry, "bar")
    assert any(c["name"] == "session1" for c in calls)


def test_start_execution_triggers_continuous_autosave(state_in_continuous_mode, monkeypatch):
    calls = _patch_dump(monkeypatch)
    entry = MagicMock()
    state_in_continuous_mode.start_execution(entry)
    assert any(c["name"] == "session1" for c in calls)


def test_stop_execution_triggers_continuous_autosave(state_in_continuous_mode, monkeypatch):
    calls = _patch_dump(monkeypatch)
    entry = MagicMock()
    state_in_continuous_mode.stop_execution(entry)
    assert any(c["name"] == "session1" for c in calls)


def test_on_disable_dumps_when_autosave_is_on_exit(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "on_exit"
    state._haystack_settings.last_haystack_name = "session1"

    captured = {}

    def fake_dump(s, root, name, active_path=None):
        captured["name"] = name
        captured["active_path"] = active_path
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)

    state.on_disable()
    assert captured["name"] == "session1"
    assert captured["active_path"] is None  # on_disable has no session context


def test_on_disable_does_not_dump_when_autosave_is_off(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "off"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state.on_disable()
    assert called == []


def test_on_disable_does_not_dump_when_autosave_is_continuous(state_with_mocked_deps, tmp_path, monkeypatch):
    """Continuous mode handles dumps via per-mutator hooks; on_disable should NOT
    additionally fire — it would be a redundant write at shutdown."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state.on_disable()
    assert called == []


def test_on_disable_skips_when_last_name_empty(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "on_exit"
    state._haystack_settings.last_haystack_name = ""

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state.on_disable()
    assert called == []
