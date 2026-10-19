"""SkinFactory tells every card of a node about a reload of the skin that card draws with."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from haywire.ui.skin.factory import SkinFactory

pytestmark = pytest.mark.unit


def _factory() -> SkinFactory:
    return SkinFactory(skin_registry=MagicMock(), widget_factory=MagicMock())


def _reloaded(factory: SkinFactory, key: str) -> None:
    event = SimpleNamespace(
        registry_key=key,
        event_type=SimpleNamespace(value="reloaded"),
        library_identity=SimpleNamespace(label="lib"),
    )
    factory._listen_on_skin_lifecycle_event([event])  # type: ignore[list-item]


def test_a_node_drawn_with_two_skins_hears_a_reload_of_either() -> None:
    factory = _factory()
    patch_card, stage_card = MagicMock(), MagicMock()
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:Split", patch_card)
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:StackedStage", stage_card)

    _reloaded(factory, "lib:skin:Split")

    patch_card.assert_called()


def test_a_card_that_changes_skin_stops_hearing_its_old_skin() -> None:
    factory = _factory()
    card = MagicMock()
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:Old", card)
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:New", card)

    _reloaded(factory, "lib:skin:Old")
    card.assert_not_called()

    _reloaded(factory, "lib:skin:New")
    card.assert_called_once()


def test_a_removed_card_hears_nothing_while_the_other_card_still_does() -> None:
    factory = _factory()
    patch_card, stage_card = MagicMock(), MagicMock()
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:Split", patch_card)
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:StackedStage", stage_card)

    factory.remove_factory_lifecycle_subscriber("n1", patch_card)
    _reloaded(factory, "lib:skin:Split")
    _reloaded(factory, "lib:skin:StackedStage")

    patch_card.assert_not_called()
    stage_card.assert_called()


def test_widget_tracking_ends_with_the_last_card() -> None:
    factory = _factory()
    patch_card, stage_card = MagicMock(), MagicMock()
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:Split", patch_card)
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:StackedStage", stage_card)

    factory.remove_factory_lifecycle_subscriber("n1", patch_card)
    factory._widget_factory.unregister_widget_for_node.assert_not_called()  # type: ignore[attr-defined]

    factory.remove_factory_lifecycle_subscriber("n1", stage_card)
    factory._widget_factory.unregister_widget_for_node.assert_called_once_with("n1")  # type: ignore[attr-defined]


def test_tearing_down_one_card_keeps_the_other_cards_reloads(monkeypatch) -> None:
    from haybale_graph_editor.editors.graph_canvas.ui_node import UINode

    factory = _factory()
    ui_node = UINode.__new__(UINode)
    ui_node.factory = factory
    ui_node._node_id = "n1"
    ui_node.current_ui_card = None
    monkeypatch.setattr(ui_node, "_unsubscribe_slot_fields", lambda: None)
    other_card = MagicMock()
    own_card = ui_node._listen_on_factory_lifecycle_event
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:Split", own_card)
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:StackedStage", other_card)

    ui_node.teardown_subscriptions()
    _reloaded(factory, "lib:skin:StackedStage")

    other_card.assert_called()
