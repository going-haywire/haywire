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
