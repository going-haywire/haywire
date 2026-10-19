"""A skin can own resources that a card's cleanup releases (``BaseSkin.on_card_cleanup``)."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import Client

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.skin.base import BaseSkin

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _noop_page() -> None:
    pass


class _OwningSkin(BaseSkin):
    """Registers a fresh spy per render."""

    def __init__(self) -> None:
        super().__init__(widget_factory=MagicMock())
        self.spies: list[MagicMock] = []

    def render(self, main_card, wrapper, *, on_stage):
        spy = MagicMock()
        self.spies.append(spy)
        self.on_card_cleanup(wrapper.node_id, spy)


@pytest.fixture
def drawn(library_system):
    graph = BaseGraph(filestem="cleanup", validation_scheduler=SyncScheduler())
    wrapper = make_node(graph, "haybale-testing:node:TestAddFloatNode")
    skin = _OwningSkin()
    client = Client(cast(Any, _noop_page), request=None)

    def draw():
        with client:
            return skin._render(wrapper)

    return skin, draw


def test_a_skin_cleanup_runs_when_the_card_is_cleaned_up(drawn) -> None:
    skin, draw = drawn
    card = draw()
    skin.spies[0].assert_not_called()

    card.cleanup()

    skin.spies[0].assert_called_once()


def test_a_skin_cleanup_runs_once(drawn) -> None:
    skin, draw = drawn
    card = draw()

    card.cleanup()
    card.cleanup()

    skin.spies[0].assert_called_once()


def test_a_skin_cleanup_belongs_to_one_render(drawn) -> None:
    skin, draw = drawn
    first = draw()
    draw()

    first.cleanup()

    skin.spies[0].assert_called_once()
    skin.spies[1].assert_not_called()
