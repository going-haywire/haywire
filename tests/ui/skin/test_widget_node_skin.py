"""The widget-node skin: label left, then the declared outlet's control; pins only off the stage."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest
from nicegui import Client, ui

from haybale_core.keys import WIDGET_NODE_SKIN
from haybale_core.nodes.widgets.menu import MenuNode
from haybale_core.nodes.widgets.slider import FloatSliderNode
from haybale_core.skins.widget_node_skin import WidgetNodeSkin
from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.node.layout import PATCH, STAGE, LayoutChannel
from haywire.core.node.promotion import promote_setting, set_promoted_show_widget
from haywire.core.types.enums import PortType, ShowWidgetStrategy
from haywire.ui.skin.factory import SkinFactory
from tests.conftest import edit_route, make_node

pytestmark = pytest.mark.integration


def _noop_page() -> None:
    pass


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


def _card(library_system, graph: BaseGraph, wrapper, channel: LayoutChannel) -> UINode:
    with Client(cast(Any, _noop_page), request=None):
        container = ui.element("div")
        ui_node = UINode(
            container,
            wrapper,
            library_system.injector.get(SkinFactory),
            edit_route(Editor(graph, library_system.get_node_factory())),
            channel=channel,
        )
        ui_node.refresh(ChangeReason.NODE_ADDED)
    return ui_node


def _on_stage(graph: BaseGraph, cls: Any):
    wrapper = make_node(graph, cls.class_identity.registry_key)
    assert isinstance(wrapper.node, cls)
    wrapper.node.props.on_stage = True
    graph._validation.force_immediate_validation()
    return wrapper


def _with(ui_node: UINode, prop: str) -> list[Any]:
    return [e for e in ui_node.container.descendants() if prop in e._props]


def _operable(ui_node: UINode) -> list[Any]:
    return [e for e in ui_node.container.descendants() if e._props.get("data-hw-requires") == "operate"]


def _pins(ui_node: UINode) -> list[Any]:
    return _with(ui_node, "data-pin-id")


def test_the_key_names_the_skin() -> None:
    assert WIDGET_NODE_SKIN == WidgetNodeSkin.class_identity.registry_key


def test_the_skin_draws_the_label_then_the_control(library_system, held_graph) -> None:
    wrapper = _on_stage(held_graph, FloatSliderNode)
    card = _card(library_system, held_graph, wrapper, STAGE)
    try:
        assert card._skin_key() == WIDGET_NODE_SKIN
        labels = _with(card, "data-widget-node-label")
        assert [label.text for label in labels] == [wrapper.node.display_label]
        assert len(_operable(card)) == 1
    finally:
        card.teardown_subscriptions()


def test_the_skin_draws_only_the_declared_outlet_widget(library_system, held_graph) -> None:
    wrapper = _on_stage(held_graph, FloatSliderNode)
    promote_setting(wrapper.node, "range", "max", direction=PortType.INLET)
    max_port = type(wrapper.node.range).__dict__["max"].storage_key
    set_promoted_show_widget(wrapper.node, max_port, ShowWidgetStrategy.ALWAYS)
    card = _card(library_system, held_graph, wrapper, STAGE)
    try:
        assert len(_operable(card)) == 1
    finally:
        card.teardown_subscriptions()


def test_on_stage_the_skin_draws_no_pins(library_system, held_graph) -> None:
    wrapper = _on_stage(held_graph, FloatSliderNode)
    card = _card(library_system, held_graph, wrapper, STAGE)
    try:
        assert _pins(card) == []
    finally:
        card.teardown_subscriptions()


def test_on_a_patch_canvas_it_draws_every_pin(library_system, held_graph) -> None:
    wrapper = _on_stage(held_graph, FloatSliderNode)
    promote_setting(wrapper.node, "range", "max", direction=PortType.INLET)
    wrapper.node.props.skin = WIDGET_NODE_SKIN
    card = _card(library_system, held_graph, wrapper, PATCH)
    try:
        pins = {e._props["data-pin-id"]: e._props["data-pin-dir-x"] for e in _pins(card)}
        max_port = type(wrapper.node.range).__dict__["max"].storage_key
        assert pins == {"in": "-1", max_port: "-1", "value": "1"}
    finally:
        card.teardown_subscriptions()


def test_the_skin_ignores_detail() -> None:
    skin = WidgetNodeSkin.__new__(WidgetNodeSkin)
    assert skin.honours_detail(on_stage=True) is False
    assert skin.honours_detail(on_stage=False) is False


def test_a_menu_fed_an_unknown_item_keeps_it(library_system, held_graph) -> None:
    wrapper = _on_stage(held_graph, MenuNode)
    card = _card(library_system, held_graph, wrapper, STAGE)
    try:
        with card.container.client:
            wrapper.node.ports["value"].set_value("Four")
        assert wrapper.node.ports["value"].get_value() == "Four"
    finally:
        card.teardown_subscriptions()


# ---------------------------------------------------------------------------
# The style bag (slice 5d-3b)
# ---------------------------------------------------------------------------


def _styled_card(library_system, graph: BaseGraph, **style: Any) -> tuple[UINode, Any]:
    wrapper = _on_stage(graph, FloatSliderNode)
    for name, value in style.items():
        setattr(wrapper.node.style, name, value)
    return _card(library_system, graph, wrapper, STAGE), wrapper


def _node_card(ui_node: UINode) -> Any:
    return next(e for e in ui_node.container.descendants() if "node-card" in e._classes)


def _label(ui_node: UINode) -> Any:
    return next(iter(_with(ui_node, "data-widget-node-label")))


def _face(ui_node: UINode) -> Any:
    return next(iter(_with(ui_node, "data-widget-node-face")))


def test_default_style_draws_todays_face(library_system, held_graph) -> None:
    card, _ = _styled_card(library_system, held_graph)
    try:
        assert "sf-label" in _label(card)._classes
        assert any("sf-widget" in e._classes for e in _operable(card))
        assert "width" not in _label(card)._style
        assert "--hw-max-label-width" not in _face(card)._style
        assert _node_card(card)._style.get("background") == "transparent"
        assert "border" not in _node_card(card)._style
        assert _face(card)._props["data-widget-node-face"] == "left"
    finally:
        card.teardown_subscriptions()


def test_a_node_without_a_style_bag_draws_the_default_face(library_system, held_graph) -> None:
    wrapper = _on_stage(held_graph, FloatSliderNode)
    object.__setattr__(wrapper.node, "style", None)
    card = _card(library_system, held_graph, wrapper, STAGE)
    try:
        assert "sf-label" in _label(card)._classes
        assert _node_card(card)._style.get("background") == "transparent"
    finally:
        card.teardown_subscriptions()


def test_label_typography_reaches_the_label(library_system, held_graph) -> None:
    card, _ = _styled_card(
        library_system,
        held_graph,
        font="mono",
        font_size=20,
        bold=True,
        italic=True,
        label_color="#ff0000",
        label_align="right",
    )
    try:
        style = _label(card)._style
        assert style["font-family"].startswith("ui-monospace")
        assert style["font-size"] == "20px"
        assert style["font-weight"] == "700"
        assert style["font-style"] == "italic"
        assert style["color"] == "#ff0000"
        assert style["text-align"] == "right"
    finally:
        card.teardown_subscriptions()


def test_background_and_border_reach_the_card(library_system, held_graph) -> None:
    card, _ = _styled_card(library_system, held_graph, background="#203040", border=True)
    try:
        style = _node_card(card)._style
        assert style["background"] == "#203040"
        assert style["border"].startswith("var(--hw-node-border-width)")
    finally:
        card.teardown_subscriptions()


def test_label_above_stacks_label_over_control(library_system, held_graph) -> None:
    card, _ = _styled_card(library_system, held_graph, label_position="above")
    try:
        assert _face(card)._props["data-widget-node-face"] == "above"
        assert "sf-label" not in _label(card)._classes
    finally:
        card.teardown_subscriptions()


def test_label_hidden_draws_no_label(library_system, held_graph) -> None:
    card, _ = _styled_card(library_system, held_graph, label_position="hidden")
    try:
        assert _face(card)._props["data-widget-node-face"] == "hidden"
        assert _with(card, "data-widget-node-label") == []
        assert len(_operable(card)) == 1
    finally:
        card.teardown_subscriptions()


@pytest.mark.parametrize("position", ["left", "above", "hidden"])
def test_max_label_width_applies_only_on_the_left(library_system, held_graph, position) -> None:
    card, _ = _styled_card(library_system, held_graph, label_position=position, max_label_width=80)
    try:
        carriers = [e for e in card.container.descendants() if "--hw-max-label-width" in e._style]
        if position == "left":
            assert [e._style["--hw-max-label-width"] for e in carriers] == ["80px"]
        else:
            assert carriers == []
    finally:
        card.teardown_subscriptions()
