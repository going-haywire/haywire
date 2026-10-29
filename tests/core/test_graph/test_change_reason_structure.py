"""``ChangeReason.mutates_structure``: which batches must wait for the frame barrier (ADR 0064)."""

import pytest

from haywire.core.graph.types import ChangeReason

_NON_STRUCTURAL = {
    ChangeReason.NODE_VALUE_CHANGED,
    ChangeReason.GRAPH_CONTENT_CHANGED,
    ChangeReason.NODE_REDRAW_REQUESTED,
    ChangeReason.NODE_MOVED,
    ChangeReason.NODE_STAGE_CHANGED,
    ChangeReason.NODE_LAYOUT_CHANGED,
    ChangeReason.EDGE_REDRAW_REQUESTED,
    ChangeReason.EDGE_STYLE_CHANGED,
}


@pytest.mark.unit
@pytest.mark.parametrize("reason", list(ChangeReason), ids=lambda r: r.name)
def test_mutates_structure_table(reason: ChangeReason):
    assert reason.mutates_structure() is (reason not in _NON_STRUCTURAL)
