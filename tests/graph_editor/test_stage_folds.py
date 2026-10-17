"""A fold toggled from a stage card flips the node's one fold state, and the patch card follows."""

from __future__ import annotations

from typing import Any, cast

import pytest
from nicegui import ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.skin.factory import SkinFactory

pytestmark = [pytest.mark.integration]

_CLIENT: list[Any] = []


def _noop_page() -> None:
    pass


@pytest.fixture
def nicegui_slot_context():
    """Keep a valid NiceGUI default slot active (copied from ``tests/ui/skin/conftest.py``)."""
    from nicegui import Client

    if not _CLIENT:
        _CLIENT.append(Client(cast(Any, _noop_page), request=None))
    with _CLIENT[0]:
        yield


def _render(factory: SkinFactory, wrapper, *, on_stage: bool, route=None):
    key = factory._skin_registry.get_default_skin_registry_key()
    assert key
    with ui.element("div"):
        card = factory.render(key, wrapper, on_stage=on_stage, route=route)
    assert card is not None
    return card.get_card()


def _header(card):
    headers = [e for e in card.descendants() if "data-hw-fold-id" in e._props]
    assert len(headers) == 1
    return headers[0]


def _labels(card) -> list[str]:
    return [e.text for e in card.descendants() if isinstance(e, ui.label)]


def test_toggling_a_fold_on_a_stage_card_changes_the_node_and_the_patch_follows(
    library_system, nicegui_slot_context
) -> None:
    from haybale_testing.nodes.testbed.display_node import DisplayNode

    from haywire.barn.builtin.types import FLOAT

    factory = library_system.injector.get(SkinFactory)
    graph = BaseGraph(filestem="stage folds", validation_scheduler=SyncScheduler())
    wrapper = graph.create_node_wrapper(DisplayNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    with wrapper.node.fold("Adv", default=False):
        wrapper.node.add(
            FLOAT.as_config(
                "eps", label="Epsilon", default=1.0, widget_key="haywire-core:widget:NumberWidget"
            )
        )
    fold_id = _header(_render(factory, wrapper, on_stage=True))._props["data-hw-fold-id"]
    assert wrapper.node.value(fold_id) is False

    from haywire.core.access import LevelMode
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.graph.editor import Editor

    editor = Editor(graph, library_system.get_node_factory())
    route = EditRoute(lambda: editor, lambda: LevelMode.EDIT)
    stage_card = _render(factory, wrapper, on_stage=True, route=route)
    click = next(h for h in _header(stage_card)._event_listeners.values() if h.type == "click")
    click.handler()

    assert wrapper.node.value(fold_id) is True
    assert "Epsilon" in _labels(_render(factory, wrapper, on_stage=True))
    assert "Epsilon" in _labels(_render(factory, wrapper, on_stage=False))
