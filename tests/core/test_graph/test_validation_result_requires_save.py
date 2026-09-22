"""``ValidationResult.requires_save`` decides whether a batch dirties the file.

The question is about *persistence*, not repainting, and it spans all three
change collections. The graph reason is the one easily missed: an edit made
inside a Subgraph reaches the host as a graph reason alone, naming no node of
the host's own, so a gate that scanned only nodes and edges left the host clean
while its interior changed.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.types import ChangeReason, ValidationResult

pytestmark = pytest.mark.unit


def test_an_empty_batch_saves_nothing() -> None:
    assert ValidationResult().requires_save() is False


@pytest.mark.parametrize(
    "reason",
    [ChangeReason.NODE_REDRAW_REQUESTED, ChangeReason.EDGE_REDRAW_REQUESTED],
)
def test_a_bare_repaint_does_not_save(reason: ChangeReason) -> None:
    assert ValidationResult(nodes={"n1": reason}).requires_save() is False
    assert ValidationResult(edges={"e1": reason}).requires_save() is False


@pytest.mark.parametrize(
    "reason",
    [
        ChangeReason.NODE_MOVED,  # position is persisted
        ChangeReason.NODE_LAYOUT_CHANGED,  # port order is persisted
        ChangeReason.NODE_ADDED,
        ChangeReason.NODE_REMOVED,
        ChangeReason.NODE_VALIDATION_REQUESTED,
    ],
)
def test_a_persisted_node_change_saves(reason: ChangeReason) -> None:
    assert ValidationResult(nodes={"n1": reason}).requires_save() is True


@pytest.mark.parametrize(
    "reason",
    [ChangeReason.EDGE_ADDED, ChangeReason.EDGE_REMOVED, ChangeReason.EDGE_PORT_CHANGED],
)
def test_a_persisted_edge_change_saves(reason: ChangeReason) -> None:
    assert ValidationResult(edges={"e1": reason}).requires_save() is True


def test_a_graph_reason_alone_saves() -> None:
    """What carries a Subgraph's interior edit out to its host."""
    result = ValidationResult(graph=ChangeReason.GRAPH_REQUIRE_REASSEMBLY)

    assert result.requires_save() is True


def test_one_real_change_outweighs_a_repaint() -> None:
    """A repaint batched with a real change must not mask it."""
    result = ValidationResult(
        nodes={"n1": ChangeReason.NODE_REDRAW_REQUESTED, "n2": ChangeReason.NODE_ADDED}
    )

    assert result.requires_save() is True


def test_a_canvas_resize_alone_does_not_save() -> None:
    """Canvas size is derived from node positions and is not serialized."""
    result = ValidationResult(canvas_size=(4000, 3000))

    assert result.requires_save() is False
