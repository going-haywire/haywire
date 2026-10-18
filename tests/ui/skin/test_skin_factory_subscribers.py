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
