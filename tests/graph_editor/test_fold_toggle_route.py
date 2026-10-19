"""A click on a fold's header writes through the card's edit route: undo, unsaved and level mode apply."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest
from nicegui import ui

from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.undo.config import UndoConfig
from haywire.ui.skin.factory import SkinFactory

pytestmark = [pytest.mark.integration]

_CLIENT: list[Any] = []


def _noop_page() -> None:
    pass


@pytest.fixture
def nicegui_slot_context():
    from nicegui import Client

    if not _CLIENT:
        _CLIENT.append(Client(cast(Any, _noop_page), request=None))
    with _CLIENT[0]:
        yield


class _Mode:
    def __init__(self) -> None:
        self.value = LevelMode.EDIT

    def __call__(self) -> LevelMode:
        return self.value


@pytest.fixture
def setup(library_system, nicegui_slot_context) -> Iterator[tuple]:
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    graph = BaseGraph(
        filestem="fold route", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    wrapper = graph.create_node_wrapper(FoldProbeNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    graph._validation.force_immediate_validation()
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    editor = Editor(graph, library_system.get_node_factory(), undo_config=config)
    mode = _Mode()
    route = EditRoute(lambda: editor, mode)
    yield graph, wrapper, editor, mode, route, library_system.injector.get(SkinFactory)
    graph._validation.clear()
    graph.cleanup()


def _render(factory: SkinFactory, wrapper, route: EditRoute, skin_key: str | None = None) -> ui.element:
    key = skin_key or factory._skin_registry.get_default_skin_registry_key()
    assert key
    with ui.element("div") as container:
        factory.render(key, wrapper, route=route)
    return container


def _header(container: ui.element, fold_id: str) -> ui.element:
    return next(e for e in container.descendants() if e._props.get("data-hw-fold-id") == fold_id)


def _click(header: ui.element) -> None:
    listener = next(lis for lis in header._event_listeners.values() if lis.type == "click")
    assert listener.handler is not None
    listener.handler()


def _labels(container: ui.element) -> list[str]:
    return [e.text for e in container.descendants() if isinstance(e, ui.label)]


def test_an_edit_fold_toggle_is_one_undo_step(setup) -> None:
    graph, wrapper, editor, _mode, route, factory = setup
    assert wrapper.node.value("solver") is True

    _click(_header(_render(factory, wrapper, route), "solver"))

    assert wrapper.node.value("solver") is False
    assert editor.can_undo() is True
    editor.undo()
    assert wrapper.node.value("solver") is True


def test_an_operate_fold_toggle_marks_unsaved_and_records_nothing(setup) -> None:
    graph, wrapper, editor, mode, route, factory = setup
    mode.value = LevelMode.OPERATE

    _click(_header(_render(factory, wrapper, route), "solver"))

    assert wrapper.node.value("solver") is False
    assert editor.can_undo() is False
    result = graph._validation.force_immediate_validation()
    assert result is not None
    assert result.graph is ChangeReason.GRAPH_CONTENT_CHANGED


def test_a_view_fold_toggle_is_refused(setup) -> None:
    graph, wrapper, editor, mode, route, factory = setup
    mode.value = LevelMode.VIEW
    header = _header(_render(factory, wrapper, route), "solver")

    _click(header)

    assert wrapper.node.value("solver") is True
    assert header._props["data-hw-fold-open"] == "true"
    assert editor.can_undo() is False


def test_undoing_a_fold_toggle_redraws_the_card(setup) -> None:
    graph, wrapper, editor, _mode, route, factory = setup
    _click(_header(_render(factory, wrapper, route), "solver"))
    graph._validation.force_immediate_validation()

    editor.undo()

    result = graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes.get(wrapper.node_id) is ChangeReason.NODE_REDRAW_REQUESTED


def test_the_split_skin_draws_a_fold_as_one_toggle_row(setup) -> None:
    from haybale_graph_editor.skins.split_skin import SplitNodeSkin

    graph, wrapper, _editor, _mode, route, factory = setup
    split_key = SplitNodeSkin.class_identity.registry_key
    card = _render(factory, wrapper, route, skin_key=split_key)
    assert wrapper.node.value("advanced") is False
    assert _labels(card).count("Advanced") == 1
    # epsilon, the closed fold's one child, has no label of its own: it shows as "Float".
    closed_floats = _labels(card).count("Float")

    _click(_header(card, "advanced"))

    assert wrapper.node.value("advanced") is True
    reopened = _render(factory, wrapper, route, skin_key=split_key)
    assert _labels(reopened).count("Advanced") == 1
    assert _labels(reopened).count("Float") == closed_floats + 1
    assert len([e for e in reopened.descendants() if e._props.get("data-hw-fold-id") == "advanced"]) == 1
