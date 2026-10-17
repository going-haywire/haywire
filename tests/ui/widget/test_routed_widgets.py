"""A widget writes through the model its host built; a routed model sends each write to an ``EditRoute``."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from nicegui import Client, ui

from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.types.base import BaseType
from haywire.core.types.fields import DataField
from haywire.core.types.port import DataPort
from haywire.ui.panel.port_default_widget_model import PortDefaultWidgetModel
from haywire.ui.panel.setting_widget_model import SettingWidgetModel
from haywire.ui.skin.factory import SkinFactory
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.factory import WidgetFactory

from tests.conftest import make_node
from tests.ui.widget._sync_fixtures import _RecordingElement, make_float_port

_NUMBER_WIDGET = "haywire-core:widget:NumberWidget"


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


def _route(graph: BaseGraph, library_system, mode: LevelMode) -> EditRoute:
    editor = Editor(graph, library_system.get_node_factory())
    return EditRoute(lambda: editor, lambda: mode)


def _render(library_system, port: Any, node_id: str, **kwargs: Any) -> BaseWidget:
    factory = library_system.injector.get(WidgetFactory)
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        widget, _element = factory.render_widget(_NUMBER_WIDGET, port, node_id, **kwargs)
    assert isinstance(widget, BaseWidget)
    return widget


def _add_node(graph: BaseGraph) -> Any:
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    return make_node(graph, TestAddFloatNode.class_identity.registry_key)


# =============================================================================
# The factory builds a routed model
# =============================================================================


@pytest.mark.integration
def test_a_port_widget_writes_through_its_route(library_system, held_graph: BaseGraph):
    wrapper = _add_node(held_graph)
    held_graph._validation.force_immediate_validation()
    port = wrapper.node.ports["value_a"]
    route = _route(held_graph, library_system, LevelMode.EDIT)
    widget = _render(library_system, port, wrapper.node_id, route=route, minimum=LevelMode.OPERATE)

    widget.set_value(4.0)

    assert port.data.get_own_value() == 4.0
    result = held_graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}


@pytest.mark.integration
def test_a_route_below_the_minimum_refuses_and_snaps_back(library_system, held_graph: BaseGraph):
    wrapper = _add_node(held_graph)
    held_graph._validation.force_immediate_validation()
    port = wrapper.node.ports["value_a"]
    route = _route(held_graph, library_system, LevelMode.VIEW)
    widget = _render(library_system, port, wrapper.node_id, route=route, minimum=LevelMode.OPERATE)

    with patch.object(widget, "on_model_changed") as shown:
        widget.set_value(9.0)

    assert port.data.get_own_value() == 0.0
    shown.assert_called_once_with(0.0)
    assert held_graph._validation.force_immediate_validation() is None


@pytest.mark.integration
def test_a_port_widget_without_a_route_is_read_only(library_system, held_graph: BaseGraph):
    wrapper = _add_node(held_graph)
    held_graph._validation.force_immediate_validation()
    port = wrapper.node.ports["value_a"]
    widget = _render(library_system, port, wrapper.node_id)

    with patch.object(widget, "on_model_changed") as shown:
        widget.set_value(9.0)

    assert port.data.get_own_value() == 0.0
    shown.assert_called_once_with(0.0)
    assert held_graph._validation.force_immediate_validation() is None


@pytest.mark.integration
def test_a_linked_port_refuses_through_a_route_that_allows(library_system, held_graph: BaseGraph):
    wrapper = _add_node(held_graph)
    held_graph._validation.force_immediate_validation()
    port = wrapper.node.ports["value_a"]
    port.set_value(4.0)
    route = _route(held_graph, library_system, LevelMode.EDIT)
    widget = _render(library_system, port, wrapper.node_id, route=route, minimum=LevelMode.OPERATE)
    port.incoming.linked["e1"] = cast(Any, object())
    port.set_value(5.0, edge_id="e1")
    held_graph._validation.force_immediate_validation()

    assert widget.accepts_write() is False
    widget.set_value(9.0)

    assert port.data.get_own_value() == 4.0
    assert held_graph._validation.force_immediate_validation() is None


@pytest.mark.integration
def test_a_port_of_no_node_is_read_only_even_with_a_route(library_system):
    port = make_float_port()
    widget = _render(library_system, port, "n1", route=MagicMock(spec=EditRoute))

    widget.set_value(9.0)

    assert port.data.get_own_value() == 0.0


@pytest.mark.integration
def test_a_promoted_port_widget_writes_its_setting(
    library_system, held_graph: BaseGraph, make_node_with_setting
):
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting()
    promote_setting(node, "filter", "threshold")
    descriptor = type(node.filter).__dict__["threshold"]
    port = node.ports[descriptor.storage_key]
    route = _route(held_graph, library_system, LevelMode.EDIT)
    widget = _render(library_system, port, node.node_id, route=route, minimum=LevelMode.OPERATE)

    widget.set_value(0.25)

    assert node.filter.threshold == 0.25
    assert node.filter._is_locally_set("threshold") is True


@pytest.mark.integration
def test_a_model_the_host_built_is_used_as_given(library_system):
    port = make_float_port()
    model = PortDefaultWidgetModel(port, on_edit=lambda _v: None)

    widget = _render(library_system, model, "dialog", route=MagicMock(spec=EditRoute))

    assert widget.port is model


# =============================================================================
# Widgets write through their model
# =============================================================================


@dataclass
class _Vec2(BaseType):
    x: float = 0.0
    y: float = 0.0


class _RecordingModel:
    """A ``WidgetModel`` over a real cell that records each write instead of applying it."""

    def __init__(self, cell: DataField) -> None:
        self.id = "v"
        self.widget_config: dict[str, Any] = {}
        self._cell = cell
        self.writes: list[Any] = []

    @property
    def data(self) -> DataField:
        return self._cell

    def get_value(self) -> Any:
        return self._cell.get_value()

    def set_value(self, value: Any) -> bool:
        self.writes.append(value)
        return True


class _Vec2Widget(BaseWidget):
    def build(self) -> Any:
        self.ex = _RecordingElement()
        self.bind(self.ex, to="x")
        return self.ex


@pytest.mark.unit
def test_a_nested_binding_writes_a_new_value_through_the_model():
    from haywire.core.types.enums import PortType

    port = DataPort(
        registry_id="vec2",
        registry_key="test:type:vec2",
        label="V",
        id="v",
        type_cls=_Vec2,
        port_type=PortType.INLET,
    )
    original = _Vec2(x=1.0, y=2.0)
    port.set_value(original)
    model = _RecordingModel(port.data)
    widget = _Vec2Widget(cast(Any, model))
    widget.render()

    widget.ex.value = 9.0
    widget.ex.handlers["update:modelValue"](type("E", (), {"sender": widget.ex})())

    assert len(model.writes) == 1
    assert model.writes[0] == _Vec2(x=9.0, y=2.0)
    assert model.writes[0] is not original
    assert original == _Vec2(x=1.0, y=2.0)


@pytest.mark.integration
def test_an_optional_inner_edit_goes_through_the_outer_model():
    from haywire.barn.builtin import widgets as builtin_widgets
    from haywire.barn.builtin.types import INT, OPTIONAL
    from haywire.barn.builtin.widgets.optional_widget import OptionalWidget
    from haywire.ui.widget.globals import WIDGET_REGISTRY

    before = dict(WIDGET_REGISTRY)
    WIDGET_REGISTRY[builtin_widgets.NumberWidget.class_identity.registry_key] = builtin_widgets.NumberWidget
    try:
        wrapper: Any = OPTIONAL
        cell = wrapper[INT].create_field(default_override={"value": 5})
        edits: list[Any] = []

        def refuse(value: Any) -> bool:
            edits.append(value)
            return False

        model = SettingWidgetModel("opt", {"properties": {}}, cell, refuse)
        outer = OptionalWidget(model)
        with Client(cast(Any, _noop_page), request=None):
            outer.render()
        inner = cast(Any, outer)._inner

        with patch.object(inner, "on_model_changed") as shown:
            inner.set_value(7)

        assert edits == [7]
        assert cell.get_value() == 5
        shown.assert_called_once_with(5)
    finally:
        WIDGET_REGISTRY.clear()
        WIDGET_REGISTRY.update(before)


# =============================================================================
# Skins hand their card widgets the route
# =============================================================================


@pytest.mark.integration
def test_a_skin_hands_its_card_widgets_the_route(
    library_system, held_graph: BaseGraph, nicegui_slot_context
):
    wrapper = _add_node(held_graph)
    port = wrapper.node.ports["value_a"]
    route = MagicMock(spec=EditRoute)
    route.set_port.return_value = True
    skin_factory = library_system.injector.get(SkinFactory)
    key = skin_factory._skin_registry.get_default_skin_registry_key()
    assert key

    with ui.element("div"):
        card = skin_factory.render(key, wrapper, route=route)

    assert card is not None
    widgets = [
        widget
        for widget in card.widget_instances.values()
        if isinstance(widget, BaseWidget) and widget.port.data is port.data
    ]
    assert len(widgets) == 1
    widgets[0].set_value(9.0)

    route.set_port.assert_called_once_with(wrapper.node_id, "value_a", 9.0, minimum=LevelMode.OPERATE)
