"""Stage skin fields, skin tags and the tag-filtered skin lists (slice 5d-1, Task 1)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.registry import SkinRegistry

pytestmark = [pytest.mark.integration]


def _skin_cls(name: str, **kwargs) -> type[BaseSkin]:
    """A throwaway skin class decorated with ``@skin(**kwargs)``."""

    class _S(BaseSkin):
        def render(self, main_card, wrapper, **_kwargs):  # pragma: no cover - never drawn
            return None

    _S.__name__ = name
    _S.__qualname__ = name
    return skin(registry_id=name, label=name, **kwargs)(_S)


@pytest.fixture
def registry():
    """A fresh skin registry that the skin choice lists read from."""
    reg = SkinRegistry()
    with patch("haywire.core.di.config.get_skin_registry", return_value=reg):
        yield reg


def test_skin_choices_need_every_include_and_no_exclude(registry) -> None:
    from haywire.core.skin.settings import skin_choices

    general = _skin_cls("General", tags=["general"])
    stage_only = _skin_cls("StageOnly", tags=["general", "stage-only"])
    special = _skin_cls("Special", tags=["special", "x"])
    for cls in (general, stage_only, special):
        registry._register_class(cls)

    assert list(skin_choices(include=["general"], exclude=["stage-only"])) == [
        general.class_identity.registry_key
    ]
    assert list(skin_choices(include=["special", "x"])) == [special.class_identity.registry_key]
    assert skin_choices(include=["special", "y"]) == {}


def test_an_untagged_skin_is_general(registry) -> None:
    from haywire.core.skin.settings import _patch_skin_choices, _stage_skin_choices

    plain = _skin_cls("Plain")
    registry._register_class(plain)

    assert plain.class_identity.tags == ["general"]
    assert plain.class_identity.registry_key in _patch_skin_choices()
    assert plain.class_identity.registry_key in _stage_skin_choices()


def test_a_special_skin_is_in_no_general_list(registry) -> None:
    from haywire.core.skin.settings import _patch_skin_choices, _stage_skin_choices

    special = _skin_cls("OnlyForSomeNodes", tags=["special", "stage-only", "widget-node"])
    registry._register_class(special)

    assert special.class_identity.registry_key not in _patch_skin_choices()
    assert special.class_identity.registry_key not in _stage_skin_choices()


def test_a_stage_only_skin_is_in_the_stage_list_only(registry) -> None:
    from haywire.core.skin.settings import _patch_skin_choices, _stage_skin_choices

    twin = _skin_cls("Twin", tags=["general", "stage-only"])
    registry._register_class(twin)

    assert twin.class_identity.registry_key not in _patch_skin_choices()
    assert twin.class_identity.registry_key in _stage_skin_choices()


def test_every_skin_field_uses_its_views_list() -> None:
    from haywire.core.graph.properties import GraphProperties
    from haywire.core.node.properties import NodeProperties
    from haywire.core.skin.settings import (
        NodeDefaultSkinSettings,
        _patch_skin_choices,
        _stage_skin_choices,
    )

    def options(owner, name):
        return type.__getattribute__(owner, name).widget_config["properties"]["options"]

    assert options(NodeDefaultSkinSettings, "studio_skin") is _patch_skin_choices
    assert options(GraphProperties, "default_skin") is _patch_skin_choices
    assert options(NodeProperties, "skin") is _patch_skin_choices
    assert options(NodeDefaultSkinSettings, "studio_stage_skin") is _stage_skin_choices
    assert options(GraphProperties, "default_stage_skin") is _stage_skin_choices
    assert options(NodeProperties, "stage_skin") is _stage_skin_choices


def test_the_studio_stage_skin_defaults_to_the_default_skin() -> None:
    from haywire.core.skin.settings import NodeDefaultSkinSettings, _default_skin

    descriptor = type.__getattribute__(NodeDefaultSkinSettings, "studio_stage_skin")
    assert descriptor._default is _default_skin


def _node(graph: BaseGraph):
    from haybale_testing.nodes.testbed.display_node import DisplayNode

    wrapper = graph.create_node_wrapper(DisplayNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    assert wrapper.node is not None
    return wrapper.node


def test_the_stage_skin_chain_resolves_node_then_graph_then_framework(library_system) -> None:
    from haywire.core.skin.settings import _default_skin

    graph = BaseGraph(filestem="stage skin chain", validation_scheduler=SyncScheduler())
    node = _node(graph)
    framework = _default_skin()

    assert node.props.stage_skin == framework

    graph.props.default_stage_skin = "graph:skin:G"
    assert node.props.stage_skin == "graph:skin:G"

    node.props.stage_skin = "node:skin:N"
    assert node.props.stage_skin == "node:skin:N"

    node.props.skin = "node:skin:Patch"
    assert node.props.stage_skin == "node:skin:N"


def test_a_patch_skin_never_reaches_the_stage_chain(library_system) -> None:
    from haywire.core.skin.settings import _default_skin

    graph = BaseGraph(filestem="stage skin no inherit", validation_scheduler=SyncScheduler())
    node = _node(graph)

    graph.props.default_skin = "graph:skin:PatchOnly"
    node.props.skin = "node:skin:PatchOnly"

    assert node.props.stage_skin == _default_skin()


def test_annotation_and_reroute_bind_their_own_stage_skin(library_system) -> None:
    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.barn.builtin.nodes.reroute import RerouteNode

    graph = BaseGraph(filestem="bound stage skins", validation_scheduler=SyncScheduler())
    for cls in (AnnotationNode, RerouteNode):
        wrapper = graph.create_node_wrapper(cls.class_identity.registry_key, position=(0, 0))
        assert wrapper is not None
        assert wrapper.node is not None
        assert wrapper.node.props.stage_skin == wrapper.node.props.skin


def test_a_built_port_saves_no_tags_key(library_system) -> None:
    from haywire.barn.builtin.types import FLOAT

    graph = BaseGraph(filestem="port tags", validation_scheduler=SyncScheduler())
    node = _node(graph)
    node.add(FLOAT.as_inlet("x_tags", default=1.0))

    assert "tags" not in node.ports["x_tags"].to_dict()["kwargs"]
