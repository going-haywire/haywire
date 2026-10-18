"""A stage render is the patch card with only on-stage pins."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from nicegui import ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types.enums import LayoutDirection
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.factory import SkinFactory
from haywire.ui.skin.pin_render import render_pin

from tests.conftest import make_edge, make_node

pytestmark = [pytest.mark.integration]


@pytest.fixture
def ctx(library_system, nicegui_slot_context):
    skin_factory = library_system.injector.get(SkinFactory)
    graph = BaseGraph(filestem="stage render", validation_scheduler=SyncScheduler())
    return skin_factory, graph


def _wrapper(graph):
    from haybale_testing.nodes.testbed.display_node import DisplayNode

    from haywire.barn.builtin.types import ANNOTATION, EXEC, FLOAT

    wrapper = graph.create_node_wrapper(DisplayNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    # DisplayNode's own widget keys name a library that is not loaded, so give it
    # an inlet with a widget that resolves.
    wrapper.node.add(FLOAT.as_inlet("x", default=1.0, widget_key="haywire-core:widget:NumberWidget"))
    wrapper.node.add(EXEC.as_inlet("flow"))
    wrapper.node.add(ANNOTATION.as_swinglet("note"))
    return wrapper


def _render(ctx, wrapper, *, on_stage, skin_key=None):
    skin_factory, _graph = ctx
    key = skin_key or skin_factory._skin_registry.get_default_skin_registry_key()
    assert key
    with ui.element("div"):
        card = skin_factory.render(key, wrapper, on_stage=on_stage)
    assert card is not None
    return card


def _pins(el: ui.element) -> list:
    return [e for e in el.descendants() if "data-pin-id" in e._props and "data-pin-data-type" in e._props]


def _ghosts(el: ui.element) -> list:
    return [e for e in el.descendants() if "data-pin-ghost" in e._props]


def _labels(el: ui.element) -> list[str]:
    return [e.text for e in el.descendants() if isinstance(e, ui.label)]


def _stacked_key() -> str:
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    return StackedNodeSkin.class_identity.registry_key


def test_the_stage_card_has_the_patch_cards_classes_and_title(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card()
    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()

    assert set(stage_card._classes) == set(patch_card._classes)
    assert stage_card._style == patch_card._style
    assert wrapper.node.display_label in _labels(stage_card)


def _row_labels(wrapper, card) -> list[str]:
    """Labels of the node's port rows (the title and fold headers are not port rows)."""
    port_labels = {p.label for p in wrapper.node.ports.values()}
    return [t for t in _labels(card) if t in port_labels]


def test_the_stage_row_labels_are_those_of_ports_with_a_shown_widget(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card()

    expected = {
        p.label for p in wrapper.node.ports.values() if p.widget_key is not None and p.should_show_widget()
    }
    ports = wrapper.node.ports
    assert ports["x"].label in expected
    assert set(_row_labels(wrapper, stage_card)) == expected
    assert {ports["flow"].label, ports["note"].label} <= set(_row_labels(wrapper, patch_card))


def test_a_no_widget_data_port_has_no_label_and_no_pin_on_stage(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()

    assert wrapper.node.ports["flow"].label not in _row_labels(wrapper, stage_card)
    assert "flow" not in {e._props["data-pin-id"] for e in _pins(stage_card)}


def test_a_no_widget_annotation_swinglet_has_its_pin_and_no_label_on_stage(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    note = wrapper.node.ports["note"]
    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()

    assert note.label not in _labels(stage_card)
    assert [e._props["data-pin-id"] for e in _pins(stage_card)] == ["note"]


@pytest.mark.parametrize(
    "direction",
    [LayoutDirection.LEFT_TO_RIGHT, LayoutDirection.TOP_TO_BOTTOM, LayoutDirection.BOTTOM_TO_TOP],
)
def test_the_patch_render_is_unchanged_by_the_stage_rule(ctx, direction: LayoutDirection) -> None:
    graph = ctx[1]
    wrapper = _wrapper(graph)
    graph.props.layout_direction = direction.value

    card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card()

    assert {"x", "flow", "note"} <= {e._props["data-pin-id"] for e in _pins(card)}
    if not direction.is_vertical:
        ports = wrapper.node.ports
        assert {ports[i].label for i in ("x", "flow", "note")} <= set(_row_labels(wrapper, card))


def test_the_stage_card_has_only_on_stage_pins_and_its_widgets(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key())

    assert [e._props["data-pin-id"] for e in _pins(card.get_card())] == ["note"]
    assert "x" in card.widget_instances
    assert card.get_widget_instance("x") is not None


def test_the_patch_card_is_unchanged(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key())

    pin_ids = {e._props["data-pin-id"] for e in _pins(card.get_card())}
    assert {"x", "flow", "note"} <= pin_ids


def test_ghost_pins_draw_on_stage(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    stage = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card()

    assert _ghosts(stage)
    assert len(_ghosts(stage)) == len(_ghosts(patch_card))


def test_a_collapsed_node_draws_expanded_on_stage(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    wrapper.node.props.collapsed = False
    expanded_labels = _labels(_render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card())
    expanded_stage = _labels(_render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card())

    wrapper.node.props.collapsed = True
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card()
    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()

    assert len(_labels(patch_card)) < len(expanded_labels)
    assert _labels(stage_card) == expanded_stage
    assert len(_labels(stage_card)) > len(_labels(patch_card))


@pytest.mark.parametrize("direction", [LayoutDirection.TOP_TO_BOTTOM, LayoutDirection.BOTTOM_TO_TOP])
def test_the_stage_render_in_a_vertical_layout_has_only_on_stage_pins(
    ctx, direction: LayoutDirection
) -> None:
    graph = ctx[1]
    wrapper = _wrapper(graph)
    graph.props.layout_direction = direction.value
    assert LayoutDirection.coerce(graph.props.layout_direction).is_vertical

    patch_before = {
        e._props["data-pin-id"]
        for e in _pins(_render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card())
    }
    stage = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()
    patch_after = {
        e._props["data-pin-id"]
        for e in _pins(_render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card())
    }

    # a stage card draws the on-stage pins only; the note swinglet is the node's one
    assert [e._props["data-pin-id"] for e in _pins(stage)] == ["note"]
    # a stage card reads left to right whatever the node's layout direction
    assert {e._props["data-hw-layout"] for e in _pins(stage)} == {LayoutDirection.LEFT_TO_RIGHT.value}
    assert _ghosts(stage)
    assert {"x", "flow", "note"} <= patch_before
    assert patch_after == patch_before


def test_a_reroute_on_an_annotation_wire_draws_both_pins_on_stage(ctx, library_system) -> None:
    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.core.graph.editor import Editor
    from haywire.core.node.layout import STAGE

    skin_factory, graph = ctx
    editor = Editor(graph, library_system.get_node_factory())
    key = AnnotationNode.class_identity.registry_key
    a = make_node(graph, key, position=(0, 0))
    b = make_node(graph, key, position=(400, 0))
    edge = make_edge(graph, a.node_id, "bottom_0", b.node_id, "top_0")

    reroute_id = _split(editor, edge.edge_id, STAGE)

    reroute = graph.get_node_wrapper(reroute_id)
    assert reroute is not None
    assert reroute.node.props.on_stage is True
    assert len(reroute.node.ports) == 2
    assert all(p.on_stage for p in reroute.node.ports.values())
    card = _render(ctx, reroute, on_stage=True, skin_key=_reroute_key()).get_card()
    assert {e._props["data-pin-id"] for e in _pins(card)} == set(reroute.node.ports)


def test_a_reroute_on_a_non_annotation_wire_draws_no_pins_on_stage(ctx, library_system) -> None:
    from haywire.core.graph.editor import Editor
    from haywire.core.node.layout import STAGE

    _skin_factory, graph = ctx
    editor = Editor(graph, library_system.get_node_factory())
    source = make_node(graph, "haybale-testing:node:TestAddFloatNode", position=(0, 0))
    sink = make_node(graph, "haybale-testing:node:TestAddFloatNode", position=(300, 0))
    edge = make_edge(graph, source.node_id, "result", sink.node_id, "value_a")

    reroute_id = _split(editor, edge.edge_id, STAGE)

    reroute = graph.get_node_wrapper(reroute_id)
    assert reroute is not None
    card = _render(ctx, reroute, on_stage=True, skin_key=_reroute_key()).get_card()
    assert _pins(card) == []
    patch_card = _render(ctx, reroute, on_stage=False, skin_key=_reroute_key()).get_card()
    assert len(_pins(patch_card)) == 2


def _reroute_key() -> str:
    from haywire.barn.builtin.skins.reroute_skin import RerouteSkin

    return RerouteSkin.class_identity.registry_key


def _split(editor, edge_id: str, channel) -> str:
    reroute_cls = editor._node_factory.get_reroute_node()
    assert reroute_cls is not None
    reroute_id = editor.split_edge_with_reroute(
        edge_id, (150.0, 40.0), registry_key=reroute_cls.class_identity.registry_key, channel=channel
    )
    assert reroute_id is not None
    return reroute_id


def test_an_annotation_on_stage_draws_its_text_pins_and_slots_but_no_control_pin(ctx) -> None:
    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.barn.builtin.skins.annotation_skin import AnnotationSkin
    from haywire.barn.builtin.types import ADD

    _skin_factory, graph = ctx
    key = AnnotationNode.class_identity.registry_key
    a = make_node(graph, key, position=(0, 0))
    b = make_node(graph, key, position=(400, 0))
    make_edge(graph, a.node_id, "bottom_0", b.node_id, "top_0")
    make_edge(graph, a.node_id, "done", b.node_id, "exec")
    graph.force_validation()
    assert a.node.ports["done"].is_linked()

    skin_key = AnnotationSkin.class_identity.registry_key
    card = _render(ctx, a, on_stage=True, skin_key=skin_key).get_card()

    assert "Double-click to write" in _labels(card)
    pin_ids = {e._props["data-pin-id"] for e in _pins(card)}
    assert "exec" not in pin_ids
    assert "done" not in pin_ids
    drawn_slots = {
        p.id
        for p in a.node.ports.values()
        if p.type_cls is not None and issubclass(p.type_cls, ADD) and p.has_pin()
    }
    assert drawn_slots
    assert drawn_slots <= pin_ids
    grown = {p.id for p in a.node.ports.values() if p.on_stage and p.has_pin()}
    assert grown <= pin_ids
    # the same card on the patch draws the control pins too
    patch_pins = {
        e._props["data-pin-id"] for e in _pins(_render(ctx, a, on_stage=False, skin_key=skin_key).get_card())
    }
    assert "done" in patch_pins


def test_render_pin_on_stage_skips_a_port_that_is_not_on_stage(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    ports = wrapper.node.ports

    def draw(port_id: str, *, on_stage: bool):
        return render_pin(
            ports[port_id],
            wrapper.node_id,
            pin_gutter=18,
            card_padding=0,
            pin_protrusion=0,
            on_stage=on_stage,
        )

    assert draw("flow", on_stage=True) is None
    assert draw("x", on_stage=True) is None
    assert draw("note", on_stage=True) is not None
    assert draw("flow", on_stage=False) is not None


def test_a_skin_without_the_on_stage_keyword_fails_loudly(ctx) -> None:
    class OldSkin(BaseSkin):
        def render(self, main_card, wrapper):  # type: ignore[override]
            return None

    skin = OldSkin(widget_factory=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        skin._render(_wrapper(ctx[1]), on_stage=False)


@pytest.mark.parametrize("on_stage", [False, True])
def test_the_error_fallback_forwards_on_stage(ctx, on_stage: bool) -> None:
    skin_factory, graph = ctx
    key = _stacked_key()
    error_key = skin_factory._skin_registry.get_error_skin_registry_key()
    assert error_key
    assert key != error_key
    skin = skin_factory.get_skin_instance(key)
    error_skin = skin_factory.get_skin_instance(error_key)
    seen: list[bool] = []
    real_render = type(error_skin).render

    def boom(self, card, wrapper, *, on_stage):
        raise RuntimeError("boom")

    def spy(self, card, wrapper, *, on_stage):
        seen.append(on_stage)
        return real_render(self, card, wrapper, on_stage=on_stage)

    with (
        patch.object(type(skin), "render", boom),
        patch.object(type(error_skin), "render", spy),
    ):
        card = _render(ctx, _wrapper(graph), on_stage=on_stage, skin_key=key)
    assert card is not None
    assert seen == [on_stage]


def _split_key() -> str:
    from haybale_studio.skins.split_skin import SplitNodeSkin

    return SplitNodeSkin.class_identity.registry_key


def _fold_ids(el: ui.element) -> list[str]:
    return [e._props["data-hw-fold-id"] for e in el.descendants() if "data-hw-fold-id" in e._props]


def _fold_wrapper(graph, *, default: bool):
    from haywire.barn.builtin.types import FLOAT

    wrapper = _wrapper(graph)
    with wrapper.node.fold("Adv", default=default):
        wrapper.node.add(
            FLOAT.as_config(
                "eps", label="Epsilon", default=1.0, widget_key="haywire-core:widget:NumberWidget"
            )
        )
    return wrapper


def _fold_state(card) -> list[str]:
    return [e._props["data-hw-fold-open"] for e in card.descendants() if "data-hw-fold-open" in e._props]


def test_an_open_fold_draws_its_header_and_children_on_stage(ctx) -> None:
    wrapper = _fold_wrapper(ctx[1], default=True)
    eps = wrapper.node.ports["eps"]

    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card()

    assert _fold_ids(stage_card) == _fold_ids(patch_card) != []
    assert _fold_state(stage_card) == ["true"]
    assert eps.label in _labels(stage_card)
    assert eps.label in _labels(patch_card)


def test_a_closed_fold_draws_its_header_and_hides_its_children_on_stage(ctx) -> None:
    wrapper = _fold_wrapper(ctx[1], default=False)
    eps = wrapper.node.ports["eps"]

    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card()

    assert _fold_ids(stage_card) == _fold_ids(patch_card) != []
    assert _fold_state(stage_card) == ["false"]
    assert eps.label not in _labels(stage_card)
    assert eps.label not in _labels(patch_card)


@pytest.mark.parametrize("default", [True, False])
def test_a_fold_whose_widget_is_hidden_draws_no_header_and_children_follow_its_state(
    ctx, default: bool
) -> None:
    from haywire.core.types.enums import ShowWidgetStrategy

    wrapper = _fold_wrapper(ctx[1], default=default)
    wrapper.node.ports["Adv".lower()].set_show_widget(ShowWidgetStrategy.NEVER)
    eps = wrapper.node.ports["eps"]

    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_stacked_key()).get_card()
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_stacked_key()).get_card()

    assert _fold_ids(stage_card) == []
    assert (eps.label in _labels(stage_card)) is default
    assert len(_fold_ids(patch_card)) == 1


def test_the_split_skin_config_band_honours_fold_state_on_stage(ctx) -> None:
    wrapper = _fold_wrapper(ctx[1], default=False)
    eps = wrapper.node.ports["eps"]

    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_split_key()).get_card()
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_split_key()).get_card()

    assert eps.label not in _labels(stage_card)
    assert eps.label not in _labels(patch_card)

    wrapper.node.ports["adv"].set_value(True)
    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_split_key()).get_card()
    assert eps.label in _labels(stage_card)


def test_the_split_skin_draws_no_empty_config_band_on_stage(ctx) -> None:
    from haywire.core.types.enums import ShowWidgetStrategy
    from haywire.barn.builtin.types import FLOAT

    wrapper = _wrapper(ctx[1])
    wrapper.node.add(
        FLOAT.as_config("bare", label="Bare", default=1.0, show_widget=ShowWidgetStrategy.NEVER)
    )
    assert not wrapper.node.ports["bare"].should_show_widget()

    stage_card = _render(ctx, wrapper, on_stage=True, skin_key=_split_key()).get_card()
    patch_card = _render(ctx, wrapper, on_stage=False, skin_key=_split_key()).get_card()

    assert "Config" not in _labels(stage_card)
    assert "Config" in _labels(patch_card)


def test_render_pin_marks_on_stage_pins(ctx) -> None:
    wrapper = _wrapper(ctx[1])
    ports = wrapper.node.ports

    def draw(port_id: str):
        return render_pin(
            ports[port_id], wrapper.node_id, pin_gutter=18, card_padding=0, pin_protrusion=0, on_stage=False
        )

    assert "data-pin-on-stage" in draw("note")._props
    assert "data-pin-on-stage" not in draw("x")._props
    assert "data-pin-on-stage" not in draw("flow")._props


def test_the_default_skins_ignore_detail_on_stage_only(ctx) -> None:
    skin_factory, _graph = ctx
    for key in (_stacked_key(), _split_key()):
        skin = skin_factory.get_skin_instance(key)
        assert skin.honours_detail(on_stage=False) is True
        assert skin.honours_detail(on_stage=True) is False


def test_a_skin_honours_detail_in_both_views_by_default() -> None:
    from haywire.barn.builtin.skins.annotation_skin import AnnotationSkin

    skin = AnnotationSkin(widget_factory=None)  # type: ignore[arg-type]
    assert skin.honours_detail(on_stage=True) is True
    assert skin.honours_detail(on_stage=False) is True
