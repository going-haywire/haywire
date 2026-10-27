"""BaseSkin.render_setting_widget: a settings field's widget on a card, writing through the card's route."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import ui

from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.skin.base import BaseSkin

from tests.conftest import make_node

pytestmark = pytest.mark.integration


class _Skin(BaseSkin):
    def render(self, main_card, wrapper, *, on_stage):  # pragma: no cover - not drawn here
        raise NotImplementedError


@pytest.fixture
def note(library_system):
    from haywire.barn.builtin.nodes.annotation import AnnotationNode

    graph = BaseGraph(filestem="setting widget", validation_scheduler=SyncScheduler())
    wrapper = make_node(graph, AnnotationNode.class_identity.registry_key)
    yield wrapper
    graph.cleanup()


def _factory() -> tuple[MagicMock, ui.element]:
    element = ui.element("div")
    factory = MagicMock()
    factory.render_widget.return_value = (None, element)
    return factory, element


def _draw(skin: _Skin, wrapper, name: str, route: Any = None, **kwargs: Any) -> ui.element | None:
    skin._nodeids_routes[wrapper.node_id] = route
    return skin.render_setting_widget(cast(Any, wrapper.node).annotation, name, wrapper.node_id, **kwargs)


def test_it_draws_the_field_s_own_widget_by_default(note, nicegui_slot_context) -> None:
    from haywire.barn.builtin.widget_keys import SELECT_WIDGET

    factory, _ = _factory()
    _draw(_Skin(factory), note, "font")

    assert factory.render_widget.call_args.args[0] == SELECT_WIDGET


def test_a_widget_key_overrides_it(note, nicegui_slot_context) -> None:
    factory, _ = _factory()
    _draw(_Skin(factory), note, "text", widget_key="lib:widget:Other")

    assert factory.render_widget.call_args.args[0] == "lib:widget:Other"


def test_writes_go_through_the_route_at_operate(note, nicegui_slot_context) -> None:
    factory, _ = _factory()
    route = MagicMock()
    route.set_setting.return_value = True
    _draw(_Skin(factory), note, "font", route=route)
    model = factory.render_widget.call_args.args[1]

    assert model.set_value("serif") is True

    bag = cast(Any, note.node).annotation
    route.set_setting.assert_called_once_with(bag, "font", "serif", minimum=LevelMode.OPERATE)


def test_without_a_route_it_is_read_only(note, nicegui_slot_context) -> None:
    factory, _ = _factory()
    _draw(_Skin(factory), note, "font")
    model = factory.render_widget.call_args.args[1]

    assert model.set_value("serif") is False
    assert cast(Any, note.node).annotation.font == "sans"


def test_the_model_requires_its_fields_rule(note, nicegui_slot_context) -> None:
    factory, element = _factory()
    assert _draw(_Skin(factory), note, "font", route=MagicMock()) is element
    assert factory.render_widget.call_args.args[1].requires is LevelMode.OPERATE

    factory, element = _factory()
    assert _draw(_Skin(factory), note, "text", route=MagicMock()) is element
    assert factory.render_widget.call_args.args[1].requires is LevelMode.EDIT


def test_without_a_route_the_model_requires_nothing(note, nicegui_slot_context) -> None:
    factory, _ = _factory()
    _draw(_Skin(factory), note, "font")
    assert factory.render_widget.call_args.args[1].requires is None


def test_a_setting_widget_and_its_promoted_pin_s_widget_are_both_kept(note, nicegui_slot_context) -> None:
    """A promoted port's id is its setting's storage_key; each widget is cleaned up with the card."""
    descriptor = type(cast(Any, note.node).annotation)._settings_descriptors()["font"]
    setting_widget, pin_widget = MagicMock(name="setting"), MagicMock(name="pin")
    factory = MagicMock()
    factory.render_widget.return_value = (setting_widget, ui.element("div"))
    skin = _Skin(factory)
    _draw(skin, note, "font")
    skin._nodeids_widget_instances[note.node_id][descriptor.storage_key] = pin_widget

    assert set(skin._nodeids_widget_instances[note.node_id].values()) == {setting_widget, pin_widget}
