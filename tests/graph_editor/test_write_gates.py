"""Value writes from the canvas and the Ports panel are checked against the effective tier.

A node card's widgets need operate; the Ports panel's widgets and its port
reordering need edit, which a locked level refuses even to an admin.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from nicegui import Client, ui

from haybale_graph_editor.access import GraphWriteGate, NodeWriteGate, allows
from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import AccessTier
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason

from tests.conftest import make_node
from tests.ui.widget._sync_fixtures import _BaseDefaultFloatWidget, make_float_port


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _allows_fn(tier: AccessTier, locked: bool = False):
    return lambda required: allows(tier.satisfies, locked, required)


def _card_widget(ui_node_wrapper: Any, port: Any, tier: AccessTier) -> _BaseDefaultFloatWidget:
    """Gate one rendered card widget the way ``UINode`` gates its card."""
    widget = _BaseDefaultFloatWidget(port)
    widget.render()
    ui_node: Any = object.__new__(UINode)
    ui_node.wrapper = ui_node_wrapper
    ui_node._allows = _allows_fn(tier)
    ui_node.current_ui_card = SimpleNamespace(widget_instances={port.id: widget})
    ui_node._apply_write_gates()
    return widget


# =============================================================================
# The gates
# =============================================================================


@pytest.mark.unit
def test_node_write_gate_asks_at_call_time_and_marks_the_node():
    answers = {AccessTier.EDIT: True}
    wrapper = MagicMock()
    gate = NodeWriteGate(AccessTier.EDIT, lambda required: answers[required], wrapper)

    assert gate.allows() is True
    answers[AccessTier.EDIT] = False
    assert gate.allows() is False

    gate.written()
    wrapper.mark_value_edited.assert_called_once_with()


@pytest.mark.unit
def test_graph_write_gate_marks_nothing():
    gate = GraphWriteGate(AccessTier.EDIT, _allows_fn(AccessTier.EDIT))

    assert gate.allows() is True
    gate.written()
    assert GraphWriteGate(AccessTier.EDIT, _allows_fn(AccessTier.OPERATE)).allows() is False


# =============================================================================
# Node card widgets
# =============================================================================


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    """A graph whose debounce never fires on its own, so a test drains it explicitly."""
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.mark.integration
def test_card_widgets_get_an_operate_gate(held_graph: BaseGraph):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    wrapper = make_node(held_graph, TestAddFloatNode.class_identity.registry_key)
    held_graph._validation.force_immediate_validation()
    port = wrapper.node.ports["value_a"]

    viewer = _card_widget(wrapper, port, AccessTier.VIEW)
    viewer.set_value(9.0)
    assert port.data.get_own_value() == 0.0
    assert held_graph._validation.force_immediate_validation() is None

    operator = _card_widget(wrapper, port, AccessTier.OPERATE)
    operator.set_value(9.0)
    assert port.get_value() == 9.0
    result = held_graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}
    assert result.requires_save() is True


@pytest.mark.integration
def test_a_rendered_card_refuses_a_view_principals_write(library_system, held_graph: BaseGraph):
    """The gate reaches the card through UINode's own render, with the real skin factory."""
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from haywire.ui.skin.factory import SkinFactory
    from haywire.ui.widget.base import BaseWidget

    wrapper = make_node(held_graph, TestAddFloatNode.class_identity.registry_key)
    port = wrapper.node.ports["value_a"]
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        container = ui.element("div")
        ui_node = UINode(
            container, wrapper, library_system.injector.get(SkinFactory), _allows_fn(AccessTier.VIEW)
        )
        ui_node.refresh(ChangeReason.NODE_ADDED)
    try:
        assert ui_node.current_ui_card is not None
        widgets = [
            widget
            for widget in ui_node.current_ui_card.widget_instances.values()
            if isinstance(widget, BaseWidget) and widget.port is port
        ]
        assert len(widgets) == 1

        widgets[0].set_value(9.0)

        assert port.data.get_own_value() == 0.0
    finally:
        ui_node.teardown_subscriptions()


@pytest.mark.unit
def test_card_widgets_stay_writable_for_operate_on_a_locked_level():
    port = make_float_port()
    wrapper = MagicMock()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()
    ui_node: Any = object.__new__(UINode)
    ui_node.wrapper = wrapper
    ui_node._allows = _allows_fn(AccessTier.ADMIN, locked=True)
    ui_node.current_ui_card = SimpleNamespace(widget_instances={port.id: widget})
    ui_node._apply_write_gates()

    widget.set_value(2.0)

    assert port.get_value() == 2.0
    wrapper.mark_value_edited.assert_called_once_with()


# =============================================================================
# Ports panel
# =============================================================================


class _RecordingWidgetFactory:
    """Renders a float widget for any port and keeps the instance for the test."""

    def __init__(self) -> None:
        self.instances: list[_BaseDefaultFloatWidget] = []

    def render_widget(self, registry_key: str, port: Any, node_id: str):
        widget = _BaseDefaultFloatWidget(port)
        element = widget.render()
        self.instances.append(widget)
        return widget, element


def _ports_ctx(tier: AccessTier, locked: bool, wrapper: Any) -> Any:
    edit = SimpleNamespace(active_locked=locked, active_node=wrapper)
    return SimpleNamespace(can_access=tier.satisfies, data={EditState: edit})


def _ports_panel_widget(ctx: Any) -> _BaseDefaultFloatWidget:
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    port = make_float_port()
    port.widget_key = "test:float"
    factory = _RecordingWidgetFactory()
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            NodePortsPanel()._render_port(port, "n1", factory, ctx)
    assert len(factory.instances) == 1
    return factory.instances[0]


@pytest.mark.unit
def test_ports_panel_widgets_need_edit():
    wrapper = MagicMock()
    widget = _ports_panel_widget(_ports_ctx(AccessTier.ADMIN, locked=True, wrapper=wrapper))

    widget.set_value(9.0)

    assert widget.port.get_value() == 0.0
    wrapper.mark_value_edited.assert_not_called()


@pytest.mark.unit
def test_ports_panel_widgets_refuse_operate():
    wrapper = MagicMock()
    widget = _ports_panel_widget(_ports_ctx(AccessTier.OPERATE, locked=False, wrapper=wrapper))

    widget.set_value(9.0)

    assert widget.port.get_value() == 0.0


@pytest.mark.unit
def test_ports_panel_widgets_write_and_mark_for_edit():
    wrapper = MagicMock()
    widget = _ports_panel_widget(_ports_ctx(AccessTier.EDIT, locked=False, wrapper=wrapper))

    widget.set_value(9.0)

    assert widget.port.get_value() == 9.0
    wrapper.mark_value_edited.assert_called_once_with()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tier", "locked", "enabled"),
    [
        (AccessTier.VIEW, False, False),
        (AccessTier.OPERATE, False, False),
        (AccessTier.ADMIN, True, False),
        (AccessTier.EDIT, False, True),
    ],
)
def test_ports_panel_widgets_draw_disabled_below_edit(tier: AccessTier, locked: bool, enabled: bool):
    with patch.object(_BaseDefaultFloatWidget, "set_enabled", autospec=True) as set_enabled:
        widget = _ports_panel_widget(_ports_ctx(tier, locked=locked, wrapper=MagicMock()))

    set_enabled.assert_called_once_with(widget, enabled)


@pytest.mark.unit
def test_ports_panel_reads_the_lock_at_write_time():
    wrapper = MagicMock()
    ctx = _ports_ctx(AccessTier.ADMIN, locked=False, wrapper=wrapper)
    widget = _ports_panel_widget(ctx)

    ctx.data[EditState].active_locked = True
    widget.set_value(9.0)

    assert widget.port.get_value() == 0.0


@dataclass
class _Drop:
    old_index: int
    new_index: int


class _RecordingNode:
    def __init__(self, ids: list[str]) -> None:
        self.ids = list(ids)

    def reorder_ports(self, ordered_ids: list[str]) -> None:
        self.ids = [pid for pid in ordered_ids if pid in self.ids]


@pytest.mark.unit
def test_reordering_ports_refuses_on_a_locked_level():
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    node = _RecordingNode(["a", "b", "c"])
    ctx = _ports_ctx(AccessTier.ADMIN, locked=True, wrapper=MagicMock())

    NodePortsPanel()._on_reorder(node, ["a", "b", "c"], _Drop(old_index=2, new_index=0), ctx)

    assert node.ids == ["a", "b", "c"]


@pytest.mark.unit
def test_reordering_ports_applies_for_edit():
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    node = _RecordingNode(["a", "b", "c"])
    ctx = _ports_ctx(AccessTier.EDIT, locked=False, wrapper=MagicMock())

    NodePortsPanel()._on_reorder(node, ["a", "b", "c"], _Drop(old_index=2, new_index=0), ctx)

    assert node.ids == ["c", "a", "b"]


# =============================================================================
# Selection forms
# =============================================================================


@pytest.mark.unit
def test_a_node_form_needs_edit_and_marks_every_node():
    from haybale_graph_editor.panels._selection_forms import FormSubject, _form_gate

    first, second = MagicMock(), MagicMock()
    subject = FormSubject("neutral", nodes=[first, second])
    ctx = _ports_ctx(AccessTier.ADMIN, locked=False, wrapper=None)
    gate = _form_gate(ctx, subject)

    assert gate.allows() is True
    gate.written()
    first.mark_value_edited.assert_called_once_with()
    second.mark_value_edited.assert_called_once_with()

    ctx.data[EditState].active_locked = True
    assert gate.allows() is False


@pytest.mark.unit
def test_an_edge_form_needs_edit():
    from haybale_graph_editor.panels._selection_forms import FormSubject, _form_gate

    subject = FormSubject("own")
    assert _form_gate(_ports_ctx(AccessTier.OPERATE, locked=False, wrapper=None), subject).allows() is False
    assert _form_gate(_ports_ctx(AccessTier.EDIT, locked=False, wrapper=None), subject).allows() is True


# =============================================================================
# Edge propagation switch
# =============================================================================


def _edge_ctx(tier: AccessTier, locked: bool) -> tuple[Any, Any]:
    from haywire.core.types.enums import Propagation

    edge = SimpleNamespace(propagation=Propagation.EAGER, locked_propagation=None, redraw=MagicMock())
    edit = SimpleNamespace(active_locked=locked, active_edge=edge)
    return SimpleNamespace(can_access=tier.satisfies, data={EditState: edit}), edge


def _propagation_switch(ctx: Any) -> Any:
    """Draw the propagation panel for ``ctx``'s active edge and return its switch."""
    from haybale_graph_editor.panels.properties.introspect.edge import EdgePropagationPanel

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        layout = ui.column()
        EdgePropagationPanel().draw(ctx, cast(Any, layout))
    return next(el for el in client.elements.values() if isinstance(el, ui.switch))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tier", "locked"), [(AccessTier.ADMIN, True), (AccessTier.VIEW, False)], ids=["locked-admin", "view"]
)
def test_the_propagation_switch_refuses_below_edit(tier: AccessTier, locked: bool):
    from haywire.core.types.enums import Propagation

    ctx, edge = _edge_ctx(tier, locked)
    switch = _propagation_switch(ctx)

    assert switch.enabled is False
    switch.value = True

    assert edge.propagation is Propagation.EAGER
    assert switch.value is False
    edge.redraw.assert_not_called()


@pytest.mark.unit
def test_the_propagation_switch_refuses_once_the_level_is_locked():
    from haywire.core.types.enums import Propagation

    ctx, edge = _edge_ctx(AccessTier.ADMIN, locked=False)
    switch = _propagation_switch(ctx)

    ctx.data[EditState].active_locked = True
    switch.value = True

    assert edge.propagation is Propagation.EAGER
    assert switch.value is False


@pytest.mark.unit
def test_the_propagation_switch_writes_for_edit():
    from haywire.core.types.enums import Propagation

    ctx, edge = _edge_ctx(AccessTier.EDIT, locked=False)
    switch = _propagation_switch(ctx)

    assert switch.enabled is True
    switch.value = True

    assert edge.propagation is Propagation.LAZY
    edge.redraw.assert_called_once_with()


# =============================================================================
# Port edit dialog (the Ports panel's pen)
# =============================================================================


def _resolved_port() -> Any:
    from haywire.core.types.enums import PortOrigin

    return SimpleNamespace(
        id="p1", label="Gain", description="", widget_key=None, origin=PortOrigin.RESOLVED
    )


def _pen_ctx(tier: AccessTier, locked: bool) -> Any:
    edit = SimpleNamespace(active_locked=locked, active_node=MagicMock())
    return SimpleNamespace(can_access=tier.satisfies, data={EditState: edit}, session=MagicMock())


def _render_pen(ctx: Any) -> Any:
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            NodePortsPanel()._render_pen(_resolved_port(), "n1", None, ctx)
    return next(el for el in client.elements.values() if isinstance(el, ui.button))


def _open_dialog(ctx: Any, editor: Any) -> Client:
    """Open the pen's edit dialog for ``ctx`` against ``editor``; return its client."""
    from haybale_graph_editor.panels.properties.introspect import node_ports

    client = Client(cast(Any, _noop_page), request=None)
    with client, patch.object(node_ports, "editor_for", lambda _ctx: editor):
        node_ports.NodePortsPanel()._open_editor(_resolved_port(), "n1", ctx)
    return client


def _apply_button(client: Client) -> Any:
    return next(
        (el for el in client.elements.values() if isinstance(el, ui.button) and el.text == "Apply"), None
    )


def _apply_relabelled(client: Client, label: str) -> None:
    """Type ``label`` into the open dialog's Label field and press Apply."""
    with client:
        label_input = next(
            el
            for el in client.elements.values()
            if isinstance(el, ui.input) and el.props.get("label") == "Label"
        )
        label_input.value = label
        _fire_click(_apply_button(client))


def _fire_click(element: Any) -> None:
    listener_id = next(iter(element._event_listeners))
    element._handle_event({"listener_id": listener_id, "args": {}})


def _metadata_editor() -> Any:
    editor = MagicMock()
    editor.set_port_metadata.return_value = (True, None)
    return editor


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tier", "locked"), [(AccessTier.ADMIN, True), (AccessTier.VIEW, False)], ids=["locked-admin", "view"]
)
def test_the_port_pen_refuses_below_edit(tier: AccessTier, locked: bool):
    ctx = _pen_ctx(tier, locked)
    assert _render_pen(ctx).enabled is False

    editor = _metadata_editor()
    client = _open_dialog(ctx, editor)
    if _apply_button(client) is not None:
        _apply_relabelled(client, "Level")

    editor.set_port_metadata.assert_not_called()


@pytest.mark.unit
def test_an_open_port_dialog_refuses_once_the_level_is_locked():
    ctx = _pen_ctx(AccessTier.ADMIN, locked=False)
    editor = _metadata_editor()
    client = _open_dialog(ctx, editor)

    ctx.data[EditState].active_locked = True
    _apply_relabelled(client, "Level")

    editor.set_port_metadata.assert_not_called()


@pytest.mark.unit
def test_the_port_pen_applies_for_edit():
    ctx = _pen_ctx(AccessTier.EDIT, locked=False)
    assert _render_pen(ctx).enabled is True

    editor = _metadata_editor()
    client = _open_dialog(ctx, editor)
    _apply_relabelled(client, "Level")

    editor.set_port_metadata.assert_called_once_with("n1", "p1", label="Level")
