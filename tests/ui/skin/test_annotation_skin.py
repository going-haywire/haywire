"""The annotation skin's side table: the layout that puts a swinglet on each side, and its port ids."""

import pytest

pytestmark = pytest.mark.unit

#: The outward direction vector of each card side.
_OUTWARD = {"top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0)}


@pytest.mark.parametrize("side", ["top", "right", "bottom", "left"])
def test_each_side_has_the_layout_that_puts_a_swinglet_there(side: str) -> None:
    from haywire.barn.builtin.skins.annotation_skin import _LAYOUT

    # A swinglet sits on its layout's inlet side (LayoutDirection.side_for).
    layout = _LAYOUT[side]
    assert layout.inlet_side == side
    assert layout.inlet_vector == _OUTWARD[side]


def test_the_skin_and_the_node_parse_port_ids_alike() -> None:
    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.barn.builtin.skins.annotation_skin import _SIDES, _parse

    assert _SIDES == AnnotationNode.SIDES
    for port_id in ("top_0", "left_12", "exec", "done", "root_in", "top_x", "left_in_0"):
        assert _parse(port_id) == AnnotationNode._parse(port_id)
        parsed = _parse(port_id)
        assert (parsed[0] if parsed else None) == AnnotationNode.side_of(port_id)


@pytest.mark.integration
def test_the_card_has_no_editor_of_its_own(library_system, nicegui_slot_context) -> None:
    from nicegui import ui

    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.barn.builtin.widgets.note_text_widget import NoteTextWidget
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.ui.skin.factory import SkinFactory

    from tests.conftest import make_node

    factory = library_system.injector.get(SkinFactory)
    graph = BaseGraph(filestem="note card", validation_scheduler=SyncScheduler())
    try:
        wrapper = make_node(graph, AnnotationNode.class_identity.registry_key)
        with ui.element("div"):
            node_card = factory.render(wrapper.node.props.skin, wrapper)
        assert node_card is not None
        card = node_card.get_card()

        assert not any(lis.type == "dblclick" for lis in card._event_listeners.values())
        widgets = list(node_card.widget_instances.values())
        assert [type(w) for w in widgets] == [NoteTextWidget]
        note_root = widgets[0].ui_element
        textareas = [e for e in card.descendants() if isinstance(e, ui.textarea)]
        assert len(textareas) == 1
        assert textareas[0] in note_root.descendants()
    finally:
        graph.cleanup()
