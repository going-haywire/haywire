"""Macro documents as a second category of haystack entry.

A macro entry is open in memory, editable and saveable, but it is not a member
of the haystack: no haystack lists it, it does not reopen on the next launch,
and it cannot be executed. Releasing it is the user's explicit act.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


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
def state(settings_registry_wired):
    from haybale_haystack.state.haystack_state import HaystackState

    state = HaystackState()
    state._dispatcher = MagicMock()
    state._dispatcher.return_value = state._dispatcher
    state._workspace_root = Path("/tmp/ws")
    state._node_factory = MagicMock()
    state._library_state_container = MagicMock()
    return state


def _open(state, path: Path, *, macro: bool):
    """Open ``path`` with the graph construction mocked out."""
    path.write_text("{}")
    with patch.object(state, "_make_graph_and_editor") as mock_make:
        mock_graph = MagicMock()
        mock_graph.load_from_file.return_value = True
        mock_make.return_value = (mock_graph, MagicMock())
        return state.open_macro(path) if macro else state.open_graph(path)


# ---------------------------------------------------------------------------
# The category
# ---------------------------------------------------------------------------


def test_a_graph_opens_as_a_haystack_member(state, tmp_path):
    from haybale_haystack.graph_entry import EntryKind

    entry = _open(state, tmp_path / "g.haywire", macro=False)

    assert entry.kind is EntryKind.GRAPH
    assert entry.kind.is_haystack_member() is True
    assert entry.kind.is_executable() is True


def test_a_macro_opens_as_a_non_member(state, tmp_path):
    from haybale_haystack.graph_entry import EntryKind

    entry = _open(state, tmp_path / "Blur.hwm", macro=True)

    assert entry.kind is EntryKind.MACRO
    assert entry.kind.is_haystack_member() is False
    assert entry.kind.is_executable() is False


def test_a_macro_is_in_memory_like_any_entry(state, tmp_path):
    """It lives in _entries, which is what makes remove_entry able to release it."""
    entry = _open(state, tmp_path / "Blur.hwm", macro=True)

    assert state.get_by_id(entry.binding_id) is entry
    assert entry in state.all_entries()


def test_reopening_a_macro_returns_the_open_entry(state, tmp_path):
    """Two sessions share one entry, so a second open must not reload over edits."""
    path = tmp_path / "Blur.hwm"
    first = _open(state, path, macro=True)
    second = _open(state, path, macro=True)

    assert first is second


def test_the_two_categories_list_separately(state, tmp_path):
    from haybale_haystack.graph_entry import EntryKind

    graph = _open(state, tmp_path / "g.haywire", macro=False)
    macro = _open(state, tmp_path / "Blur.hwm", macro=True)

    assert state.entries_of_kind(EntryKind.GRAPH) == [graph]
    assert state.entries_of_kind(EntryKind.MACRO) == [macro]


# ---------------------------------------------------------------------------
# Not part of the set
# ---------------------------------------------------------------------------


def test_opening_a_macro_does_not_dirty_the_haystack(state, tmp_path):
    """Nothing about the set changed, so its dirty flag must not move."""
    _open(state, tmp_path / "Blur.hwm", macro=True)

    assert state.is_haystack_dirty is False


def test_opening_a_graph_does_dirty_the_haystack(state, tmp_path):
    _open(state, tmp_path / "g.haywire", macro=False)

    assert state.is_haystack_dirty is True


def test_a_macro_is_not_written_to_the_haystack_toml(state, tmp_path):
    """dump_haystack walks all_entries; a macro must be filtered out of it."""
    from haybale_haystack import persistence

    _open(state, tmp_path / "g.haywire", macro=False)
    _open(state, tmp_path / "Blur.hwm", macro=True)

    target = persistence.dump_haystack(state, tmp_path, "set")
    written = target.read_text()

    assert "g.haywire" in written
    assert "Blur.hwm" not in written


def test_releasing_a_macro_does_not_dirty_the_haystack(state, tmp_path):
    entry = _open(state, tmp_path / "Blur.hwm", macro=True)
    state._haystack_dirty = False

    state.remove_entry(entry)

    assert state.is_haystack_dirty is False
    assert state.get_by_id(entry.binding_id) is None


# ---------------------------------------------------------------------------
# Not executable, not renameable
# ---------------------------------------------------------------------------


def test_compiling_a_macro_is_refused_with_a_reason(state, tmp_path):
    """A macro holds no EVENT node, so a bare "nothing ran" verdict would not say why."""
    entry = _open(state, tmp_path / "Blur.hwm", macro=True)

    result = entry.compile()

    assert result.ok is False
    assert result.error is not None
    assert "macro" in result.error.lower()


def test_a_save_as_on_a_macro_is_refused(state, tmp_path):
    """A macro's filestem IS its registry key; moving it would orphan placements."""
    entry = _open(state, tmp_path / "Blur.hwm", macro=True)

    assert state._save_entry(entry, save_as=tmp_path / "Other.hwm") is False
    assert not (tmp_path / "Other.hwm").exists()


def test_a_plain_save_on_a_macro_still_works(state, tmp_path):
    """Editing and saving is the whole point — only the rename is refused."""
    entry = _open(state, tmp_path / "Blur.hwm", macro=True)
    entry.graph.save_to_file.return_value = True
    entry.unsaved = True

    assert state._save_entry(entry) is None
    assert entry.unsaved is False
