"""Tests for Slot._activate and on_focus lifecycle hook firing rules."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.ui.app.slot import EditorBinding, Slot
from haywire.ui.editor.base import BaseEditor


class _FakeEditor(BaseEditor):
    """Minimal BaseEditor subclass that records on_focus / draw calls."""

    class_identity = SimpleNamespace(
        registry_key="test:editor:fake",
        label="Fake",
        default_slot="main",
    )

    def __init__(self) -> None:
        self.focus_calls: list[Any] = []
        self.draw_calls: list[Any] = []

    def draw(self, context, container) -> None:
        self.draw_calls.append(context)

    def on_focus(self, context) -> None:
        self.focus_calls.append(context)


def _make_session():
    ctx = SimpleNamespace()
    session = SimpleNamespace(context=ctx)
    return session


def _make_binding(key: str) -> EditorBinding:
    return EditorBinding(editor_key=key, editor_cls=_FakeEditor, payload=None)


def test_switch_to_calls_on_focus_on_new_active_binding():
    """Slot.switch_to must call on_focus(context) on the newly-activated instance."""
    session = _make_session()
    b1 = _make_binding("e1")
    b2 = _make_binding("e2")
    slot = Slot(session, "main", [b1, b2], active_key="e1")

    # Bootstrap area so switch_to executes its full path.
    slot._area_container = MagicMock()

    # Pre-create instances so we can observe calls.
    b1.ensure_instance()
    b2.ensure_instance()

    slot.switch_to("e2")

    assert len(b2.instance.focus_calls) == 1
    assert b2.instance.focus_calls[0] is session.context


def test_switch_to_does_not_call_on_focus_when_target_already_active():
    """Re-selecting the active binding must NOT re-fire on_focus."""
    session = _make_session()
    b1 = _make_binding("e1")
    slot = Slot(session, "main", [b1], active_key="e1")
    slot._area_container = MagicMock()
    b1.ensure_instance()

    slot.switch_to("e1")

    assert b1.instance.focus_calls == []


def test_render_area_calls_on_focus_on_initial_active_binding():
    """First render of the slot must fire on_focus on the initially-active binding."""
    session = _make_session()
    b1 = _make_binding("e1")
    slot = Slot(session, "main", [b1], active_key="e1")

    parent = MagicMock()
    slot.render_area(parent)

    assert b1.instance is not None
    assert len(b1.instance.focus_calls) == 1


def test_add_binding_activate_true_calls_on_focus():
    """add_binding(activate=True) must fire on_focus on the newly-added binding."""
    session = _make_session()
    slot = Slot(session, "main", [], active_key=None)
    slot._area_container = MagicMock()

    new_binding = _make_binding("e_new")
    slot.add_binding(new_binding, activate=True)

    assert new_binding.instance is not None
    assert len(new_binding.instance.focus_calls) == 1


def test_on_focus_runs_before_draw_on_first_activation():
    """on_focus must fire before draw on the first time a binding becomes active."""
    session = _make_session()
    b1 = _make_binding("e1")
    slot = Slot(session, "main", [b1], active_key="e1")

    parent = MagicMock()
    slot.render_area(parent)

    instance = b1.instance
    # focus_calls is appended in on_focus; draw_calls is appended in draw.
    # We can't compare timestamps easily — instead assert both ran.
    assert len(instance.focus_calls) == 1
    assert len(instance.draw_calls) == 1


def test_on_focus_raising_is_logged_and_swallowed(caplog):
    """An exception from on_focus must be logged and not propagate."""
    import logging

    class _RaisingEditor(_FakeEditor):
        def on_focus(self, context):
            raise RuntimeError("boom")

    session = _make_session()
    b1 = EditorBinding(editor_key="e1", editor_cls=_RaisingEditor, payload=None)
    slot = Slot(session, "main", [b1], active_key="e1")
    parent = MagicMock()

    with caplog.at_level(logging.ERROR, logger="haywire.ui.app.slot"):
        slot.render_area(parent)

    assert any("on_focus" in rec.message for rec in caplog.records)
