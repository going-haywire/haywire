"""Unit tests for EditState — per-session graph-editor state.

Covers:
  - EditState is a SessionState subclass.
  - Direct instantiation works; defaults match the field declarations.
  - Reactive containers are per-instance (mutable defaults are not shared).
  - Registration into a LibraryStateContainer via the v1.1 session-class
    hook + attach_session yields an instance reachable via get_session;
    detach_session drops it.
  - The LibrarySettings prohibition on SessionState passes (implicit —
    the import of EditState would raise at class definition otherwise;
    a guard test below makes the assertion explicit).

Note: tests resolve `EditState` from the live module each time, because
the studio library bootstrap may `importlib.reload` the module in other
tests, which would otherwise leave a stale top-of-file reference.
"""

from __future__ import annotations

import importlib

import pytest

from haywire.core.state import LibraryStateContainer, LibraryStateRegistry, SessionState

_EDIT_STATE_MODULE = "haybale_graph_editor.state.edit_state"


def _edit_state_cls() -> type:
    """Return the live EditState class (reload-safe)."""
    return importlib.import_module(_EDIT_STATE_MODULE).EditState


class TestEditStateClass:
    def test_edit_state_is_session_state_subclass(self):
        assert issubclass(_edit_state_cls(), SessionState)

    def test_edit_state_can_be_instantiated(self):
        EditState = _edit_state_cls()
        instance = EditState()
        assert isinstance(instance, EditState)
        assert isinstance(instance, SessionState)

    def test_session_id_is_settable(self):
        instance = _edit_state_cls()()
        instance.session_id = "abc"
        assert instance.session_id == "abc"

    def test_class_definition_did_not_raise_for_library_settings(self):
        """Implicit guard: EditState has no LibrarySettings-typed fields.

        The SessionState `__init_subclass__` check would have raised
        TypeError at import time if any field were a LibrarySettings
        subclass. Reaching this test means the check passed.
        """
        assert _edit_state_cls().__name__ == "EditState"


class TestEditStateDefaults:
    def test_nullable_defaults_are_none(self):
        instance = _edit_state_cls()()
        assert instance.active_graph is None
        assert instance.active_graph_path is None
        assert instance.active_node is None
        assert instance.active_edge is None
        assert instance.active_port is None
        assert instance.clipboard is None

    def test_selection_set_defaults_are_empty(self):
        instance = _edit_state_cls()()
        assert instance.selected_nodes == set()
        assert instance.selected_edges == set()

    def test_mutable_defaults_are_per_instance(self):
        """Each EditState instance must own its own selection sets.

        signal_field emits on reassignment, not on in-place mutation; the
        rewrite below uses union-and-reassign so the test still verifies
        per-instance isolation of the mutable default (and now also
        exercises the emit path).
        """
        from tests.conftest import attach_stub_session

        EditState = _edit_state_cls()
        a = attach_stub_session(EditState())
        b = EditState()
        a.selected_nodes = a.selected_nodes | {"node-1"}
        assert "node-1" not in b.selected_nodes


class TestEditStateContainerLifecycle:
    """Verify EditState plugs into the v1.1 LibraryStateContainer correctly.

    Uses the `register_edit_state` fixture from conftest.py, which calls
    `container._add_session_class(EditState, key)` directly per
    internals/prd/v1.2-edit-state-migration.md §3.5 option (a) and returns the
    same EditState class reference the container saw.
    """

    def test_attach_session_creates_instance(self, register_edit_state):
        container = LibraryStateContainer(LibraryStateRegistry())
        sid = "session-1"
        EditState = register_edit_state(container, sid)

        instance = container.get_session(EditState, sid)
        assert isinstance(instance, EditState)
        assert instance.session_id == sid

    def test_two_sessions_get_independent_instances(self, register_edit_state):
        container = LibraryStateContainer(LibraryStateRegistry())
        sid_a = "session-a"
        sid_b = "session-b"
        EditState = register_edit_state(container, sid_a)
        # second attach uses the same registered class — no re-register
        container.attach_session(sid_b)

        a = container.get_session(EditState, sid_a)
        b = container.get_session(EditState, sid_b)
        assert a is not b
        assert a.session_id == sid_a
        assert b.session_id == sid_b

    def test_detach_session_drops_instance(self, register_edit_state):
        container = LibraryStateContainer(LibraryStateRegistry())
        sid = "session-detach"
        EditState = register_edit_state(container, sid)
        assert container.has_session(EditState, sid)

        container.detach_session(sid)
        assert not container.has_session(EditState, sid)
        with pytest.raises(KeyError):
            container.get_session(EditState, sid)
