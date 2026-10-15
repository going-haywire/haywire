"""Where a node goes when it is added to a graph's stage."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..node.layout import PATCH, STAGE

if TYPE_CHECKING:
    from .base import BaseGraph

#: Gap, in canvas pixels, between the stage origin and a node, and between stacked nodes.
STAGE_MARGIN = 40.0

#: Stage height assumed for a node whose height the caller does not give.
_DEFAULT_STAGE_HEIGHT = 200.0


def next_stage_spot(
    graph: "BaseGraph", count: int, heights: Sequence[float] | None = None
) -> list[tuple[float, float]]:
    """Return the stage positions for ``count`` nodes about to be added to ``graph``'s stage.

    Every spot sits at ``x = STAGE_MARGIN``. The first is ``STAGE_MARGIN`` below the lowest
    edge of the nodes already on stage, or at ``y = STAGE_MARGIN`` on an empty stage; each
    next one is ``STAGE_MARGIN`` below the one before it.

    Args:
        count: Number of nodes to place.
        heights: Stage height of each node to place, in order. A node without an entry is
            taken as 200 tall.

    Example::

        next_stage_spot(graph, 1)                       # [(40.0, 40.0)] on an empty stage
        next_stage_spot(graph, 2, heights=[100, 50])    # [(40.0, 40.0), (40.0, 180.0)]
    """
    bottoms = [
        props.stage_y + props.stage_height
        for props in (w.node.props for w in graph.node_wrappers.values())
        if STAGE.includes(props)
    ]
    y = max(bottoms) + STAGE_MARGIN if bottoms else STAGE_MARGIN

    spots: list[tuple[float, float]] = []
    for index in range(count):
        spots.append((STAGE_MARGIN, y))
        height = heights[index] if heights is not None and index < len(heights) else _DEFAULT_STAGE_HEIGHT
        y += height + STAGE_MARGIN
    return spots


def _centroid(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    return sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points)


def non_negative(xy: tuple[float, float]) -> tuple[float, float]:
    """Clamp ``xy`` to the canvas origin: nothing sits above or left of it."""
    return max(xy[0], 0.0), max(xy[1], 0.0)


def patch_position_for_stage(
    graph: "BaseGraph",
    stage_xy: tuple[float, float],
    fallback_xy: tuple[float, float] | None = None,
) -> tuple[float, float]:
    """Return the patch position for a node about to be added at stage position ``stage_xy``.

    With nodes already on stage, the node sits at the same offset from their patch centroid as
    ``stage_xy`` is from their stage centroid, so it lands near its siblings in the patch. With
    none on stage, the anchor is ``fallback_xy`` (the centre of the patch canvas's last-known
    viewport), else the centroid of all the graph's nodes, else ``stage_xy`` itself. The
    centroids are taken over the nodes now in the graph, so call this before the add. The
    result is clamped to be at least (0, 0), the patch canvas origin.

    Example::

        # siblings at stage (60, 40) and patch (900, 700): a node at stage (100, 80)
        patch_position_for_stage(graph, (100.0, 80.0))   # (940.0, 740.0)
    """
    sx, sy = stage_xy
    props = [w.node.props for w in graph.node_wrappers.values()]
    on_stage = [p for p in props if STAGE.includes(p)]
    if on_stage:
        scx, scy = _centroid([p.get_position(STAGE) for p in on_stage])
        pcx, pcy = _centroid([p.get_position(PATCH) for p in on_stage])
        return non_negative((pcx + (sx - scx), pcy + (sy - scy)))
    if fallback_xy is not None:
        return non_negative(fallback_xy)
    if props:
        return non_negative(_centroid([p.get_position(PATCH) for p in props]))
    return non_negative(stage_xy)


def stage_position_for_patch(
    graph: "BaseGraph", patch_xy: tuple[float, float]
) -> tuple[float, float] | None:
    """Return the stage position for a node about to be added at patch position ``patch_xy``.

    The node sits at the same offset from the stage centroid of the nodes already on stage as
    ``patch_xy`` is from their patch centroid, so it lands near its siblings on stage. Returns
    ``None`` when no node is on stage; the caller then picks a spot, e.g. ``next_stage_spot``.
    The result is clamped to be at least (0, 0), the stage origin. The centroids are taken over
    the nodes now in the graph, so call this before the add.

    Example::

        # siblings at stage (60, 40) and patch (900, 700): a node at patch (940, 740)
        stage_position_for_patch(graph, (940.0, 740.0))   # (100.0, 80.0)
    """
    px, py = patch_xy
    on_stage = [p for p in (w.node.props for w in graph.node_wrappers.values()) if STAGE.includes(p)]
    if not on_stage:
        return None
    scx, scy = _centroid([p.get_position(STAGE) for p in on_stage])
    pcx, pcy = _centroid([p.get_position(PATCH) for p in on_stage])
    return non_negative((scx + (px - pcx), scy + (py - pcy)))
