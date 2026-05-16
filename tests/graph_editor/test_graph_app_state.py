"""Tests for GraphAppState — the binding_id → GraphContainer registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from haybale_graph_editor.state.graph_app_state import GraphAppState


@dataclass
class _Container:
    binding_id: str
    editor: object = field(default_factory=object)
    path: Optional[Path] = None
    unsaved: bool = False
    display_name: str = "C"

    def save(self, save_as: Optional[Path] = None) -> Optional[str]:
        return None


def test_register_then_get_returns_container():
    state = GraphAppState()
    c = _Container(binding_id="a")
    state.register(c)
    assert state.get("a") is c


def test_get_unknown_id_returns_none():
    state = GraphAppState()
    assert state.get("missing") is None


def test_unregister_removes_container():
    state = GraphAppState()
    c = _Container(binding_id="a")
    state.register(c)
    state.unregister("a")
    assert state.get("a") is None


def test_unregister_unknown_id_is_noop():
    state = GraphAppState()
    state.unregister("missing")  # must not raise


def test_register_same_id_replaces():
    """Re-registering the same binding_id replaces the prior container."""
    state = GraphAppState()
    c1 = _Container(binding_id="a", display_name="first")
    c2 = _Container(binding_id="a", display_name="second")
    state.register(c1)
    state.register(c2)
    assert state.get("a") is c2


def test_rekey_moves_container():
    state = GraphAppState()
    c = _Container(binding_id="old")
    state.register(c)
    state.rekey("old", "new")
    assert state.get("old") is None
    assert state.get("new") is c


def test_rekey_unknown_old_id_is_noop():
    state = GraphAppState()
    state.rekey("missing", "anything")  # must not raise


def test_rekey_to_same_id_is_noop():
    state = GraphAppState()
    c = _Container(binding_id="a")
    state.register(c)
    state.rekey("a", "a")
    assert state.get("a") is c


def test_rekey_overwrites_existing_destination():
    """If destination key is taken, rekey replaces it.

    Rationale: rekey is called by sources after a save-as where the new
    binding_id has just been claimed by the renaming entry; collisions
    in practice mean stale state and the new claim should win.
    """
    state = GraphAppState()
    c1 = _Container(binding_id="a")
    c2 = _Container(binding_id="b")
    state.register(c1)
    state.register(c2)
    state.rekey("a", "b")
    assert state.get("a") is None
    assert state.get("b") is c1


def test_all_containers_returns_snapshot():
    state = GraphAppState()
    c1 = _Container(binding_id="a")
    c2 = _Container(binding_id="b")
    state.register(c1)
    state.register(c2)
    result = state.all_containers()
    assert len(result) == 2
    assert c1 in result
    assert c2 in result
    # Returned list is a copy — mutating it must not affect the registry.
    result.clear()
    assert state.get("a") is c1
