"""A level's edit route reaches the canvas: its cards, its structure handlers and the Ports panel.

A node card's widgets write at level mode operate; the Ports panel's widgets need
edit, which a locked level refuses even to an admin. Structure handlers do nothing
while the route hands out no ``Editor``.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from nicegui import Client, ui

from haybale_graph_editor.access import level_mode
from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers
from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import AccessTier, LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason
from haywire.ui.components.graph.event_definitions import UserDragUpdateEvent
from haywire.ui.widget.base import BaseWidget

from tests.conftest import edit_route, make_node

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    """A graph whose debounce never fires on its own, so a test drains it explicitly."""
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def editor(library_system, held_graph: BaseGraph) -> Editor:
    return Editor(held_graph, library_system.get_node_factory())


def _add_node(graph: BaseGraph) -> Any:
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    wrapper = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    graph._validation.force_immediate_validation()
    return wrapper


def _locked_admin_route(editor: Editor) -> EditRoute:
    return EditRoute(lambda: editor, lambda: level_mode(AccessTier.ADMIN.satisfies, True))


# =============================================================================
# Node cards
# =============================================================================


def _card_widget(library_system, wrapper: Any, route: EditRoute) -> tuple[BaseWidget, UINode]:
    """Render ``wrapper``'s card through UINode with ``route``; return its ``value_a`` widget."""
    from haywire.ui.skin.factory import SkinFactory

    port = wrapper.node.ports["value_a"]
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        container = ui.element("div")
        ui_node = UINode(container, wrapper, library_system.injector.get(SkinFactory), route)
        ui_node.refresh(ChangeReason.NODE_ADDED)
    assert ui_node.current_ui_card is not None
    widgets = [
        widget
        for widget in ui_node.current_ui_card.widget_instances.values()
        if isinstance(widget, BaseWidget) and widget.port.data is port.data
    ]
    assert len(widgets) == 1
    return widgets[0], ui_node


def test_a_card_widget_writes_for_operate_and_refuses_view(library_system, held_graph, editor):
    wrapper = _add_node(held_graph)
    port = wrapper.node.ports["value_a"]

    viewer, viewer_node = _card_widget(library_system, wrapper, edit_route(editor, LevelMode.VIEW))
    try:
        viewer.set_value(9.0)
    finally:
        viewer_node.teardown_subscriptions()
    assert port.data.get_own_value() == 0.0
    assert held_graph._validation.force_immediate_validation() is None

    operator, operator_node = _card_widget(library_system, wrapper, edit_route(editor, LevelMode.OPERATE))
    try:
        operator.set_value(9.0)
    finally:
        operator_node.teardown_subscriptions()
    assert port.get_value() == 9.0
    result = held_graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}
    assert result.requires_save() is True


def test_a_card_widget_stays_writable_on_a_locked_level(library_system, held_graph, editor):
    wrapper = _add_node(held_graph)

    widget, ui_node = _card_widget(library_system, wrapper, _locked_admin_route(editor))
    try:
        widget.set_value(2.0)
    finally:
        ui_node.teardown_subscriptions()

    assert wrapper.node.ports["value_a"].get_value() == 2.0


# =============================================================================
# Ports panel
# =============================================================================


class _RecordingWidgetFactory:
    """The real widget factory, keeping each widget it renders."""

    def __init__(self, factory: Any) -> None:
        self._factory = factory
        self.instances: list[BaseWidget] = []

    def render_widget(self, *args: Any, **kwargs: Any) -> Any:
        widget, element = self._factory.render_widget(*args, **kwargs)
        self.instances.append(widget)
        return widget, element


def _ports_panel_widget(library_system, wrapper: Any, route: EditRoute) -> BaseWidget:
    """Draw the Ports panel row of ``wrapper``'s ``value_a`` with ``route`` on screen; return its widget."""
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel
    from haywire.ui.widget.factory import WidgetFactory

    edit = SimpleNamespace(active_route=route, active_node=wrapper)
    ctx = SimpleNamespace(can_access=AccessTier.ADMIN.satisfies, data={EditState: edit})
    factory = _RecordingWidgetFactory(library_system.injector.get(WidgetFactory))
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            NodePortsPanel()._render_port(
                wrapper.node.ports["value_a"], wrapper.node_id, factory, cast(Any, ctx)
            )
    assert len(factory.instances) == 1
    return factory.instances[0]


def test_a_ports_panel_widget_needs_edit(library_system, held_graph, editor):
    wrapper = _add_node(held_graph)
    port = wrapper.node.ports["value_a"]

    locked = _ports_panel_widget(library_system, wrapper, _locked_admin_route(editor))
    locked.set_value(9.0)
    assert port.data.get_own_value() == 0.0
    assert held_graph._validation.force_immediate_validation() is None

    operator = _ports_panel_widget(library_system, wrapper, edit_route(editor, LevelMode.OPERATE))
    operator.set_value(9.0)
    assert port.data.get_own_value() == 0.0

    editing = _ports_panel_widget(library_system, wrapper, edit_route(editor, LevelMode.EDIT))
    editing.set_value(9.0)
    assert port.data.get_own_value() == 9.0
    result = held_graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}


def test_a_ports_panel_row_drawn_before_the_lock_refuses(library_system, held_graph, editor):
    wrapper = _add_node(held_graph)
    port = wrapper.node.ports["value_a"]
    mode = [LevelMode.EDIT]
    widget = _ports_panel_widget(library_system, wrapper, EditRoute(lambda: editor, lambda: mode[0]))

    mode[0] = LevelMode.OPERATE
    with patch.object(widget, "on_model_changed") as shown:
        widget.set_value(9.0)

    assert port.data.get_own_value() == 0.0
    shown.assert_called_once_with(0.0)


# =============================================================================
# Structure handlers
# =============================================================================


def test_structure_handlers_do_nothing_without_an_editor(held_graph, editor):
    wrapper = _add_node(held_graph)
    before = wrapper.node.props.get_position()

    InteractionHandlers(edit_route(editor, LevelMode.VIEW)).process_drag_update(
        UserDragUpdateEvent(positions={wrapper.node_id: {"x": before[0] + 500.0, "y": before[1] + 500.0}})
    )

    assert wrapper.node.props.get_position() == before
    assert editor.history_manager.can_undo() is False
