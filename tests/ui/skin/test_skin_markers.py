"""Every skin's card shows the diagnostics and comment markers: ``BaseSkin`` draws them after ``render``."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import Client, ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.node.node_warning import NodeWarning
from haywire.ui.skin.base import BaseSkin

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _noop_page() -> None:
    pass


class _PlainSkin(BaseSkin):
    """A skin that knows nothing about markers."""

    def __init__(self) -> None:
        super().__init__(widget_factory=MagicMock())

    def render(self, main_card, wrapper, *, on_stage):
        with main_card:
            ui.label("body")


class _QuietSkin(_PlainSkin):
    def render_markers(self, card, wrapper, *, on_stage):
        pass


def _markers(card: Any) -> list[str]:
    """The node ids the card's marker buttons carry, one per marker."""
    found = []
    for element in card.get_card().descendants():
        node_id = element.props.get("data-node-id")
        if isinstance(element, ui.button) and node_id:
            found.append(node_id)
    return found


@pytest.fixture
def wrapper(library_system):
    graph = BaseGraph(filestem="markers", validation_scheduler=SyncScheduler())
    return make_node(graph, "haybale-testing:node:TestAddFloatNode")


def _draw(skin: BaseSkin, wrapper: Any, *, on_stage: bool = False) -> Any:
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        return skin._render(wrapper, on_stage=on_stage)


def test_a_plain_skin_shows_the_warning_badge(wrapper) -> None:
    wrapper.state.add_warning(NodeWarning(message="careful", source_version=None, kind="compatibility"))

    assert _markers(_draw(_PlainSkin(), wrapper)) == [wrapper.node_id]


def test_a_plain_skin_shows_the_comment_badge(wrapper) -> None:
    wrapper.node.props.comment = "a note"

    assert _markers(_draw(_PlainSkin(), wrapper)) == [wrapper.node_id]


def test_a_node_with_nothing_to_mark_has_no_marker(wrapper) -> None:
    assert _markers(_draw(_PlainSkin(), wrapper)) == []


def test_the_stage_shows_no_marker(wrapper) -> None:
    wrapper.state.add_warning(NodeWarning(message="careful", source_version=None, kind="compatibility"))
    wrapper.node.props.comment = "a note"

    assert _markers(_draw(_PlainSkin(), wrapper, on_stage=True)) == []


def test_a_skin_overriding_the_hook_draws_none(wrapper) -> None:
    wrapper.state.add_warning(NodeWarning(message="careful", source_version=None, kind="compatibility"))

    assert _markers(_draw(_QuietSkin(), wrapper)) == []
