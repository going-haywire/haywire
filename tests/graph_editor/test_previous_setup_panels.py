"""Restore | Discard for a previous setup live in panels, so every skin's node can be resolved."""

from types import SimpleNamespace
from typing import Any, cast

import pytest

from haybale_graph_editor.panels import _previous_setup as previous_setup
from haybale_graph_editor.state.edit_state import EditState

pytestmark = pytest.mark.unit


def _ctx(active_node: Any) -> Any:
    return SimpleNamespace(data={EditState: SimpleNamespace(active_node=active_node)})


def test_the_panels_show_only_while_the_active_node_holds_one():
    assert previous_setup.holds_previous_setup(_ctx(SimpleNamespace(previous_setup={"x": 1})))
    assert not previous_setup.holds_previous_setup(_ctx(SimpleNamespace(previous_setup=None)))
    assert not previous_setup.holds_previous_setup(_ctx(None))


def test_the_actions_are_restore_and_discard_with_tooltips():
    assert [(label, restore) for label, _icon, _tip, restore in previous_setup.ACTIONS] == [
        ("Restore", True),
        ("Discard", False),
    ]
    assert all(tip for _label, _icon, tip, _restore in previous_setup.ACTIONS)


def test_resolve_goes_through_the_route_editor():
    calls = []

    class _Editor:
        def apply_previous_setup(self, ids):
            calls.append(("restore", ids))

        def dismiss_previous_setup(self, ids):
            calls.append(("discard", ids))

    class _Route:
        def __init__(self, editor):
            self._editor = editor

        def editor(self):
            return self._editor

    route = cast(Any, _Route)
    previous_setup.resolve_previous_setup(route(_Editor()), "n1", restore=True)
    previous_setup.resolve_previous_setup(route(_Editor()), "n2", restore=False)
    previous_setup.resolve_previous_setup(route(None), "n3", restore=True)
    previous_setup.resolve_previous_setup(None, "n4", restore=False)
    assert calls == [("restore", ["n1"]), ("discard", ["n2"])]


def test_both_panels_are_registered_on_the_menu_and_the_inspector():
    from haybale_graph_editor.panels.graph.menu.selection.selection import PreviousSetupSelectionMenuPanel
    from haybale_graph_editor.panels.properties.introspect.node import NodePreviousSetupPanel
    from haybale_graph_editor.surfaces import NodeInspector, SelectionMenu

    assert PreviousSetupSelectionMenuPanel.class_identity.surface is SelectionMenu
    assert NodePreviousSetupPanel.class_identity.surface is NodeInspector


def test_the_commands_are_stamped_edit():
    import inspect

    src = inspect.getsource(previous_setup.draw_previous_setup)
    assert "stamp_requires(command, LevelMode.EDIT)" in src
