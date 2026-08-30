"""The toolbar's collapse button — ADR 0032's fold gesture at one click.

The button is a toggle drawn once and left on screen, so the interesting part
is not that it renders: it is that it decides nothing at draw time. An earlier
version of the equivalent MENU row closed over the fold state it read while
drawing, and so folded once and then refused to unfold. These tests pin the
shape that prevents it.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel.layout import PanelLayout
from haybale_graph_editor.panels.graph.toolbar.selection import CollapseToolbarPanel
from haybale_graph_editor.surfaces import SelectionToolbar

pytestmark = pytest.mark.unit

_CLIENT: list[Any] = []


def _noop_page() -> None:
    pass


@pytest.fixture
def nicegui_slot_context():
    """Keep a valid NiceGUI default slot active for the test body.

    Copied from ``tests/ui/skin/conftest.py`` rather than imported: conftest
    fixtures do not cross sibling directories, and this file belongs beside the
    graph-editor panels it covers. The autouse ``_reset_nicegui_globals`` clears
    ``Slot.stacks`` after every test, so a bare ``ui.element`` here raises "slot
    stack is empty" the moment no earlier test happens to have left one open.
    """
    from nicegui import Client

    if not _CLIENT:
        _CLIENT.append(Client(cast(Any, _noop_page), request=None))
    with _CLIENT[0]:
        yield


class _Actions:
    """Stands in for the provider — records calls, answers like the real verb."""

    def __init__(self, collapsed: bool = False) -> None:
        self.collapsed = collapsed
        self.toggles = 0

    def selection_is_collapsed(self) -> bool:
        return self.collapsed

    def toggle_selection_collapsed(self) -> bool:
        self.toggles += 1
        self.collapsed = not self.collapsed
        return self.collapsed


def _draw(actions: _Actions):
    """Draw the panel into a throwaway container; return its button."""
    panel = CollapseToolbarPanel()
    panel.actions = actions  # type: ignore[assignment]
    container = ui.element("div")
    panel.draw(MagicMock(), PanelLayout(container))
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
    assert CollapseToolbarPanel.class_identity.surface is SelectionToolbar


def test_it_declares_no_poll_like_its_neighbours():
    """SelectionToolbar.poll is already "something is selected", and the host
    gates once before querying — restating it here would be a second copy."""
    assert "poll" not in vars(CollapseToolbarPanel)


class TestItReadsStateRatherThanCapturingIt:
    def test_initial_icon_follows_the_current_state(self, nicegui_slot_context):
        assert _draw(_Actions(collapsed=False))._props["icon"] == hui.icon.node_collapse
        assert _draw(_Actions(collapsed=True))._props["icon"] == hui.icon.node_expand

    def test_every_click_toggles(self, nicegui_slot_context):
        """The regression. A handler that closed over the draw-time state would
        send the same value forever and stop after the first press."""
        actions = _Actions(collapsed=False)
        button = _draw(actions)

        _click(button)
        assert actions.collapsed is True
        _click(button)
        assert actions.collapsed is False
        _click(button)
        assert actions.collapsed is True
        assert actions.toggles == 3

    def test_the_icon_follows_along_without_a_redraw(self, nicegui_slot_context):
        """The toolbar usually re-renders after a fold (the selection bounds
        move), but the button must not depend on that."""
        actions = _Actions(collapsed=False)
        button = _draw(actions)

        _click(button)
        assert button._props["icon"] == hui.icon.node_expand
        _click(button)
        assert button._props["icon"] == hui.icon.node_collapse

    def test_it_carries_exactly_one_tooltip_after_toggling(self, nicegui_slot_context):
        """`.tooltip()` STACKS rather than replaces, which is why the panel
        builds its own and retexts it."""
        actions = _Actions(collapsed=False)
        button = _draw(actions)

        _click(button)
        _click(button)

        tooltips = [el for el in button.descendants() if isinstance(el, ui.tooltip)]
        assert len(tooltips) == 1
        assert tooltips[0].text == "Collapse"

    def test_the_tooltip_names_the_action_not_the_state(self, nicegui_slot_context):
        """Icon and tooltip must agree — an icon showing the current state
        beside a word naming the next one reads as a contradiction."""
        actions = _Actions(collapsed=True)
        button = _draw(actions)

        tooltips = [el for el in button.descendants() if isinstance(el, ui.tooltip)]
        assert tooltips[0].text == "Expand"
        assert button._props["icon"] == hui.icon.node_expand
