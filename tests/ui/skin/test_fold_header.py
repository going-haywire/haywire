"""A fold's header on a stacked card is its FoldWidget, drawn through the skin's widget funnel."""

from __future__ import annotations

import inspect

import pytest
from nicegui import ui

from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.skin.factory import SkinFactory

pytestmark = [pytest.mark.integration]


@pytest.fixture
def card(library_system, nicegui_slot_context):
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    factory = library_system.injector.get(SkinFactory)
    graph = BaseGraph(filestem="fold header", validation_scheduler=SyncScheduler())
    wrapper = graph.create_node_wrapper(FoldProbeNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    editor = Editor(graph, library_system.get_node_factory())
    route = EditRoute(lambda: editor, lambda: LevelMode.EDIT)
    key = factory._skin_registry.get_default_skin_registry_key()
    assert key
    with ui.element("div") as container:
        factory.render(key, wrapper, route=route)
    yield container
    graph.cleanup()


def _headers(container: ui.element) -> list[ui.element]:
    return [e for e in container.descendants() if "data-hw-fold-id" in e._props]


def test_the_header_is_the_fold_widget(card) -> None:
    from haywire.barn.builtin.widgets.fold_widget import FoldWidget

    headers = _headers(card)
    assert {h._props["data-hw-fold-id"] for h in headers} == {"solver", "inputs", "advanced"}
    for header in headers:
        assert header._props.get("data-hw-requires") == "operate"
        assert any(isinstance(e, ui.icon) for e in header.descendants())
    assert FoldWidget.__name__ == "FoldWidget"


def test_the_header_has_no_click_handler_of_its_own(card) -> None:
    """Only the widget root listens for clicks: the skin's row around it writes nothing."""
    for header in _headers(card):
        row = header.parent_slot.parent if header.parent_slot is not None else None
        assert row is not None
        assert not any(lis.type == "click" for lis in row._event_listeners.values())
        assert any(lis.type == "click" for lis in header._event_listeners.values())


def test_the_widget_uses_the_central_icon_tokens() -> None:
    """Icons come from hui.icon.*, never raw Material strings."""
    from haywire.barn.builtin.widgets.fold_widget import FoldWidget

    source = inspect.getsource(FoldWidget)
    for token in ("fold_open", "fold_closed", "hui.icon.checked", "hui.icon.unchecked"):
        assert token in source
