"""The arrow-head vocabulary: one table for the canvas markers and the picker."""

import pytest

from haywire.core.edge.arrow_heads import ARROW_HEADS, NO_HEAD, ArrowHead, get_arrow_head

pytestmark = pytest.mark.unit


def test_fifteen_heads_with_unique_names():
    names = [head.name for head in ARROW_HEADS]
    assert len(names) == 15
    assert len(set(names)) == 15
    assert NO_HEAD not in names


def test_the_picker_shows_four_common_arrows_first():
    assert [head.name for head in ARROW_HEADS if head.common] == ["arrow", "sharp", "open", "triangle"]


@pytest.mark.parametrize("head", ARROW_HEADS, ids=lambda h: h.name)
def test_a_head_paints_with_the_edge_stroke_only(head: ArrowHead):
    assert head.inset > 0
    assert "context-stroke" in head.svg
    assert "#" not in head.svg  # no literal colour: a head takes the edge's paint


def test_lookup_answers_none_for_no_head_and_unknown_names():
    assert get_arrow_head(NO_HEAD) is None
    assert get_arrow_head("not-a-head") is None
    assert get_arrow_head(None) is None
    head = get_arrow_head("open")
    assert head is not None and head.label == "Open arrow"  # noqa: PT018


def test_the_payload_carries_the_marker_geometry():
    head = get_arrow_head("triangle")
    assert head is not None
    assert head.to_payload() == {
        "name": "triangle",
        "inset": 5.0,
        "svg": head.svg,
        "view_box": "-2 -4 9.0 8",
        "width": 9.0,
        "height": 8,
    }
