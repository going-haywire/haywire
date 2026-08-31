"""The toolbar's lock button — protection against accidental manipulation.

Two things are pinned here, and they are the two the design turns on.

**It polls for a SINGLE node.** Every other toolbar panel declares no ``poll``
because ``SelectionToolbar.poll`` ("something is selected") already covers it.
This one is the exception: locking is never applied to a group, and that is not
an incidental limit — it is what spares the design a mixed-state rule. With no
way to lock a set, a set is never *partly* locked, so the button has two states
to render rather than three.

**It re-reads on click.** Same regression the collapse button carries tests for:
a handler closing over the draw-time value sends the same thing forever and
stops toggling after the first press.
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
    CopyToolbarPanel,
    DeleteToolbarPanel,
    LockToolbarPanel,
)
from haybale_graph_editor.surfaces import SelectionToolbar

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


def test_it_sits_on_the_selection_toolbar():
    assert LockToolbarPanel.class_identity.surface is SelectionToolbar


def test_it_is_a_leaf():
    """A leaf is what the popup-emptiness rule counts as content."""
    assert LockToolbarPanel.class_identity.hosts == ()


class TestItAppliesToOneNodeOnly:
    """The single-selection gate — why no mixed state can exist."""

    def test_it_polls_true_for_exactly_one_selected_node(self):
        assert LockToolbarPanel.poll(_ctx(_Props(), n_selected=1)) is True

    def test_it_polls_false_for_a_multi_selection(self):
        """The whole reason there is no three-state toggle to design."""
        assert LockToolbarPanel.poll(_ctx(_Props(), n_selected=3)) is False

    def test_it_polls_false_with_nothing_selected(self):
        assert LockToolbarPanel.poll(_ctx(None, n_selected=0)) is False

    def test_it_polls_false_when_there_is_no_active_node(self):
        """A selection whose Active axis was cleared (bulk select) offers no
        single subject to lock, even at size one."""
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


class TestTheBatchVerbsGateOnLockedNotOnSelectionSize:
    """Delete and Collapse hide on a locked node — and ONLY on a locked node.

    The regression this guards: both were first gated on ``locked_bag``,
    whose "exactly one node" rule belongs to the Lock button. That hid Delete
    and Collapse from EVERY multi-selection, locked or not, quietly removing
    the delete button from ordinary batch work.
    """

    def test_delete_shows_for_a_multi_selection(self):
        assert DeleteToolbarPanel.poll(_ctx(None, n_selected=3)) is True

    def test_collapse_shows_for_a_multi_selection(self):
        assert CollapseToolbarPanel.poll(_ctx(None, n_selected=3)) is True

    def test_delete_hides_when_a_selected_node_is_locked(self):
        ctx = _ctx(_Props(locked=True), n_selected=1, locked_ids={"n0"})
        assert DeleteToolbarPanel.poll(ctx) is False

    def test_collapse_hides_when_a_selected_node_is_locked(self):
        ctx = _ctx(_Props(locked=True), n_selected=1, locked_ids={"n0"})
        assert CollapseToolbarPanel.poll(ctx) is False

    def test_one_locked_node_among_many_hides_them(self):
        """Unreachable through the canvas (locked nodes cannot join a
        multi-selection), but the predicate is written as "any" so it stays
        correct on its own terms rather than on that invariant."""
        ctx = _ctx(None, n_selected=3, locked_ids={"n1"})
        assert DeleteToolbarPanel.poll(ctx) is False

    def test_copy_stays_unconditional(self):
        """Copying a locked node harms nothing, so Copy declares no poll."""
        assert "poll" not in vars(CopyToolbarPanel)
