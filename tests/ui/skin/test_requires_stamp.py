"""A widget with a route carries ``data-hw-requires``, derived from its model; a routeless one none."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from nicegui import Client, ui

from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.access_stamp import stamp_requires
from haywire.ui.panel.render_utils import render_settings
from haywire.ui.skin.factory import SkinFactory
from haywire.ui.skin.pin_render import add_pin_tooltip

from tests.conftest import make_node
from tests.ui.panel.render_ctx import make_render_ctx

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
_SETTINGS_NODE = "haybale-testing:node:SettingsNode"
_REPO = Path(__file__).resolve().parents[3]


def _noop_page() -> None:
    pass


@pytest.fixture
def graph(library_system) -> Iterator[BaseGraph]:
    graph = BaseGraph(filestem="requires stamp", validation_scheduler=SyncScheduler())
    yield graph
    graph.cleanup()


@pytest.fixture
def route(graph: BaseGraph, library_system) -> EditRoute:
    editor = Editor(graph, library_system.get_node_factory())
    return EditRoute(lambda: editor, lambda: LevelMode.EDIT)


def _render_card(library_system, wrapper, route: EditRoute | None) -> ui.element:
    factory = library_system.injector.get(SkinFactory)
    key = factory._skin_registry.get_default_skin_registry_key()
    assert key
    with ui.element("div") as container:
        factory.render(key, wrapper, route=route)
    return container


def _requires(container: ui.element) -> dict[str, list[ui.element]]:
    """Each stamped mode, with the elements carrying it; pins (always ``view``) left out."""
    stamped: dict[str, list[ui.element]] = {}
    for element in container.descendants():
        mode = element._props.get("data-hw-requires")
        if mode is not None and "data-pin-id" not in element._props:
            stamped.setdefault(mode, []).append(element)
    return stamped


def _add_with_locked_gain(graph: BaseGraph):
    from haywire.barn.builtin.types import FLOAT
    from haywire.barn.builtin.widget_keys import NUMBER_WIDGET

    wrapper = make_node(graph, _ADD)
    wrapper.node.add(FLOAT.as_config("gain", default=1.0, operable=False, widget_key=NUMBER_WIDGET))
    assert wrapper.node.ports["gain"].operable is False
    return wrapper


def test_an_operable_card_widget_requires_operate(
    library_system, graph, route, nicegui_slot_context
) -> None:
    wrapper = make_node(graph, _ADD)
    stamped = _requires(_render_card(library_system, wrapper, route))
    assert stamped.get("operate")
    assert "edit" not in stamped


def test_a_non_operable_card_widget_requires_edit(
    library_system, graph, route, nicegui_slot_context
) -> None:
    wrapper = _add_with_locked_gain(graph)
    stamped = _requires(_render_card(library_system, wrapper, route))
    assert len(stamped.get("edit", [])) == 1
    assert stamped.get("operate")


def test_a_setting_widget_requires_its_rule(library_system, graph, route, nicegui_slot_context) -> None:
    from haywire.barn.builtin.nodes.annotation import AnnotationNode

    wrapper = make_node(graph, AnnotationNode.class_identity.registry_key)
    factory = library_system.injector.get(SkinFactory)
    key = factory._skin_registry.get_default_skin_registry_key()
    assert key
    skin = factory.get_skin_instance(key)
    skin._nodeids_routes[wrapper.node_id] = route
    bag = cast(Any, wrapper.node).annotation
    try:
        font = skin.render_setting_widget(bag, "font", wrapper.node_id)
        text = skin.render_setting_widget(bag, "text", wrapper.node_id)
    finally:
        skin._nodeids_routes.pop(wrapper.node_id, None)
    assert font is not None
    assert text is not None
    assert font._props.get("data-hw-requires") == "operate"
    assert text._props.get("data-hw-requires") == "edit"


def test_routeless_widget_is_not_stamped(library_system, graph, nicegui_slot_context) -> None:
    wrapper = _add_with_locked_gain(graph)
    assert _requires(_render_card(library_system, wrapper, None)) == {}


def _render_panel(bag: Any, route: EditRoute | None) -> ui.element:
    with Client(cast(Any, _noop_page), request=None):
        anchor = ui.column()
        with anchor:
            render_settings(make_render_ctx(), bag, route=route)
    return anchor


def _field_cells(anchor: ui.element) -> list[ui.element]:
    return [e for e in anchor.descendants() if "sf-widget" in e._classes]


def test_a_panel_settings_widget_requires_edit(graph, route) -> None:
    bag = cast(Any, make_node(graph, _SETTINGS_NODE).node).example
    anchor = _render_panel(bag, route)
    stamped = [e for e in anchor.descendants() if "data-hw-requires" in e._props]
    assert stamped
    assert {e._props["data-hw-requires"] for e in stamped} == {"edit"}
    # The row menu's writers carry the stamp too (ADR 0060); everything else stamped is a field cell.
    row_menu_items = {
        item for e in anchor.descendants() if "data-row-menu" in e._props for item in e.descendants()
    }
    assert all(e in _field_cells(anchor) or e in row_menu_items for e in stamped)
    assert any(e in _field_cells(anchor) for e in stamped)


def test_a_panel_without_route_stamps_nothing(graph) -> None:
    bag = cast(Any, make_node(graph, _SETTINGS_NODE).node).example
    anchor = _render_panel(bag, None)
    assert _field_cells(anchor)
    assert not any("data-hw-requires" in e._props for e in anchor.descendants())


def test_a_port_without_a_widget_renders_nothing(library_system, nicegui_slot_context) -> None:
    factory = library_system.injector.get(SkinFactory)
    key = factory._skin_registry.get_default_skin_registry_key()
    assert key
    port = SimpleNamespace(id="value", widget_key=None)
    assert factory.get_skin_instance(key).render_widget(port, "node-1") is None  # type: ignore[arg-type]


def test_a_readable_pin_requires_view(nicegui_slot_context) -> None:
    pin_el = ui.element("i")
    add_pin_tooltip(pin_el, SimpleNamespace(label="Gain", description=""))  # type: ignore[arg-type]
    assert pin_el._props.get("data-hw-requires") == "view"


def test_a_stamp_requires_edit_by_default_and_writes_it(nicegui_slot_context) -> None:
    element = ui.element("div")
    stamp_requires(element)
    assert element._props.get("data-hw-requires") == "edit"


def test_a_separate_tooltip_trigger_keeps_its_own_rule(nicegui_slot_context) -> None:
    host = ui.element("div")
    trigger = ui.element("div")
    add_pin_tooltip(host, SimpleNamespace(label="Gain", description=""), trigger_el=trigger)  # type: ignore[arg-type]
    assert "data-hw-requires" not in host._props
    assert "data-hw-requires" not in trigger._props


def test_no_old_marker_remains() -> None:
    result = subprocess.run(
        ["git", "grep", "-nE", "data-hw-(readable|operable)", "--", "packages", "barn", "tests"],
        capture_output=True,
        cwd=_REPO,
    )
    # git grep exits 0 on a match, 1 on none, 128 on error: only 1 proves the marker is gone.
    assert result.returncode == 1, result.stdout.decode() + result.stderr.decode()
    assert not result.stdout, result.stdout.decode()
