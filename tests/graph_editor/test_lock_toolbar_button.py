"""The toolbar's lock button — protection against accidental manipulation.

Three things are pinned here, each guarding a design rule or a real
regression rather than restating a decorator argument.

**It polls for a SINGLE node.** Every other toolbar panel declares no ``poll``
because ``SelectionToolbar.poll`` ("something is selected") already covers it.
This one is the exception: locking is never applied to a group, and that is not
an incidental limit — it is what spares the design a mixed-state rule. With no
way to lock a set, a set is never *partly* locked, so the button has two states
to render rather than three.

**It re-reads on click.** Same regression the collapse button carries tests for:
a handler closing over the draw-time value sends the same thing forever and
stops toggling after the first press.

**Collapse gates on locked, not on selection size.** A real regression: both
Collapse and its since-removed Delete-toolbar neighbour were first gated on
``locked_bag``, whose "exactly one node" rule belongs to the Lock button —
that hid them from EVERY multi-selection, locked or not.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel.layout import PanelLayout
from haybale_graph_editor.panels.graph.toolbar.selection import (
    CollapseToolbarPanel,
    LockToolbarPanel,
)

pytestmark = pytest.mark.unit

_CLIENT: list[Any] = []


def _noop_page() -> None:
    pass


@pytest.fixture
def nicegui_slot_context():
    """Keep a valid NiceGUI default slot active for the test body.

    Same shape as ``test_collapse_toolbar_button.py`` — copied rather than
    shared because conftest fixtures do not cross sibling directories.
    """
    from nicegui import Client

    if not _CLIENT:
        _CLIENT.append(Client(cast(Any, _noop_page), request=None))
    with _CLIENT[0]:
        yield


class _Props:
    """A stand-in props bag carrying just the field under test."""

    def __init__(self, locked: bool = False) -> None:
        self.locked = locked


class _DirectRoute:
    """A route that writes straight to the bag (the stub bag has no graph)."""

    def set_setting(self, bag, name, value, *, minimum) -> bool:
        setattr(bag, name, value)
        return True


def _ctx(props: _Props | None, *, n_selected: int = 1, locked_ids: set[str] = frozenset()):  # type: ignore[assignment]
    """A context whose EditState answers with `props` for the active node.

    ``locked_ids`` names selected nodes the *graph* reports as locked — what
    ``selection_has_locked`` walks, independent of the active node.
    """
    from haybale_graph_editor.state.edit_state import EditState

    edit = MagicMock()
    node_ids = {f"n{i}" for i in range(n_selected)}
    edit.selected_nodes = node_ids
    if props is None:
        edit.active_node = None
    else:
        node = MagicMock()
        node.props = props
        wrapper = MagicMock()
        wrapper.node = node
        edit.active_node = wrapper

    def get_node_wrapper(node_id: str):
        w = MagicMock()
        w.node.props.locked = node_id in locked_ids
        return w

    graph = MagicMock()
    graph.get_node_wrapper.side_effect = get_node_wrapper
    edit.active_graph = graph

    edit.active_route = _DirectRoute()

    ctx = MagicMock()
    ctx.data = {EditState: edit}
    return ctx


def _draw(ctx):
    """Draw the panel into a throwaway container; return its button."""
    panel = LockToolbarPanel()
    container = ui.element("div")
    panel.draw(ctx, PanelLayout(container))
    buttons = [el for el in container.descendants() if isinstance(el, ui.button)]
    assert len(buttons) == 1, f"expected one button, got {len(buttons)}"
    return buttons[0]


def _click(button) -> None:
    for handler in button._event_listeners.values():
        if handler.type == "click":
            handler.handler(None)
            return
    raise AssertionError("button has no click handler")


def test_it_applies_to_one_node_only():
    """The single-selection gate — why no mixed state can exist.

    With no way to lock a set, a set is never *partly* locked, so the button
    has two states to render rather than three. One test, four branches: this
    is one design rule, not four independent behaviours.
    """
    assert LockToolbarPanel.poll(_ctx(_Props(), n_selected=1)) is True
    assert LockToolbarPanel.poll(_ctx(_Props(), n_selected=3)) is False
    assert LockToolbarPanel.poll(_ctx(None, n_selected=0)) is False
    # A selection whose Active axis was cleared (bulk select) offers no single
    # subject to lock, even at size one.
    assert LockToolbarPanel.poll(_ctx(None, n_selected=1)) is False


class TestItReadsStateRatherThanCapturingIt:
    def test_initial_icon_follows_the_current_state(self, nicegui_slot_context):
        assert _draw(_ctx(_Props(locked=False)))._props["icon"] == hui.icon.unlocked
        assert _draw(_ctx(_Props(locked=True)))._props["icon"] == hui.icon.locked

    def test_every_click_toggles_the_prop(self, nicegui_slot_context):
        """The regression: a handler closing over the draw-time state would
        write the same value forever and stop after the first press."""
        props = _Props(locked=False)
        button = _draw(_ctx(props))

        _click(button)
        assert props.locked is True
        _click(button)
        assert props.locked is False
        _click(button)
        assert props.locked is True

    def test_the_icon_follows_along_without_a_redraw(self, nicegui_slot_context):
        props = _Props(locked=False)
        button = _draw(_ctx(props))

        _click(button)
        assert button._props["icon"] == hui.icon.locked
        _click(button)
        assert button._props["icon"] == hui.icon.unlocked

    def test_it_carries_exactly_one_tooltip_after_toggling(self, nicegui_slot_context):
        """`.tooltip()` STACKS rather than replaces, which is why the panel
        builds its own and retexts it."""
        props = _Props(locked=False)
        button = _draw(_ctx(props))

        _click(button)
        _click(button)

        tooltips = [el for el in button.descendants() if isinstance(el, ui.tooltip)]
        assert len(tooltips) == 1
        assert tooltips[0].text == "unlocked"

    def test_icon_and_tooltip_both_name_the_current_state(self, nicegui_slot_context):
        """This button reports STATE, unlike its Collapse neighbour, which
        names the action it will perform.

        The two conventions can coexist because the buttons answer different
        questions. Collapse is a gesture you repeat while reading a graph, so
        the useful label is what the next press does. A lock is a standing
        condition you glance at, so the useful label is what is true now — and
        a closed padlock meaning "click to lock" would read backwards against
        every padlock a user has seen. What matters either way is that icon and
        tooltip agree; one naming state beside the other naming the action is
        the contradiction to avoid.
        """
        button = _draw(_ctx(_Props(locked=True)))

        tooltips = [el for el in button.descendants() if isinstance(el, ui.tooltip)]
        assert tooltips[0].text == "locked"
        assert button._props["icon"] == hui.icon.locked


class TestCollapseGatesOnLockedNotOnSelectionSize:
    """Collapse hides on a locked node — and ONLY on a locked node.

    The regression this guards: it was first gated on ``locked_bag``, whose
    "exactly one node" rule belongs to the Lock button. That hid Collapse from
    EVERY multi-selection, locked or not, quietly removing it from ordinary
    batch work.
    """

    def test_collapse_shows_for_a_multi_selection(self):
        assert CollapseToolbarPanel.poll(_ctx(None, n_selected=3)) is True

    def test_collapse_hides_when_a_selected_node_is_locked(self):
        ctx = _ctx(_Props(locked=True), n_selected=1, locked_ids={"n0"})
        assert CollapseToolbarPanel.poll(ctx) is False

    def test_one_locked_node_among_many_hides_them(self):
        """Unreachable through the canvas (locked nodes cannot join a
        multi-selection), but the predicate is written as "any" so it stays
        correct on its own terms rather than on that invariant."""
        ctx = _ctx(None, n_selected=3, locked_ids={"n1"})
        assert CollapseToolbarPanel.poll(ctx) is False


class TestTheButtonIsAnUndoableEdit:
    """The click goes through the session's route: a recorded step in level mode edit."""

    @pytest.fixture
    def live(self, library_system):
        from haywire.core.access import LevelMode
        from haywire.core.graph.base import BaseGraph
        from haywire.core.graph.edit_route import EditRoute
        from haywire.core.graph.editor import Editor
        from haywire.core.graph.scheduler import ThreadingTimerScheduler
        from haywire.core.undo.config import UndoConfig
        from tests.conftest import make_node

        graph = BaseGraph(
            filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
        )
        editor = Editor(
            graph,
            library_system.get_node_factory(),
            undo_config=UndoConfig(enable_auto_grouping=False, enable_action_merging=True),
        )
        mode = [LevelMode.EDIT]
        route = EditRoute(lambda: editor, lambda: mode[0])
        wrapper = make_node(graph, "haybale-testing:node:TestAddFloatNode")
        yield editor, route, mode, wrapper.node.props
        graph._validation.clear()
        graph.cleanup()

    def _ctx_with_route(self, props, route):
        ctx = _ctx(cast(Any, props))
        ctx.data[next(iter(ctx.data))].active_route = route
        return ctx

    def test_the_lock_button_marks_unsaved_and_undoes(self, nicegui_slot_context, live):
        editor, route, _mode, props = live
        assert props.locked is False
        button = _draw(self._ctx_with_route(props, route))

        _click(button)

        assert props.locked is True
        assert editor.can_undo() is True
        editor.undo()
        assert props.locked is False

    def test_the_lock_button_without_edit_changes_nothing(self, nicegui_slot_context, live):
        from haywire.core.access import LevelMode

        editor, route, mode, props = live
        mode[0] = LevelMode.OPERATE
        button = _draw(self._ctx_with_route(props, route))

        _click(button)

        assert props.locked is False
        assert editor.can_undo() is False
        assert button._props["icon"] == hui.icon.unlocked
        tooltips = [el for el in button.descendants() if isinstance(el, ui.tooltip)]
        assert tooltips[0].text == "unlocked"

    def test_the_lock_button_without_a_route_changes_nothing(self, nicegui_slot_context):
        props = _Props(locked=False)
        ctx = _ctx(props)
        ctx.data[next(iter(ctx.data))].active_route = None
        button = _draw(ctx)

        _click(button)

        assert props.locked is False
        assert button._props["icon"] == hui.icon.unlocked
