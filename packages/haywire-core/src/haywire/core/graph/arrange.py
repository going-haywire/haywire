"""Auto-layout of a graph's patch view, and the node sets it acts on.

``arrange_layout`` lays a set of nodes out in layers along the graph's layout direction: each
edge points from an earlier layer to a later one, wherever the graph has no cycle. Control and
data edges count alike. The result is a dict of positions to hand to ``Editor.move_nodes_to``,
so one arrange is one undo step.

The set comes from ``connected_nodes``: the nodes downstream of a start node, upstream of it,
connected to it at all (its *flow*), or the whole graph. The start node is the anchor — it keeps
its position and the layout is placed around it. A locked node takes part in the layout but
never moves.

Pure and synchronous: it reads the graph and node props, and writes nothing.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

from ..node.layout import PATCH
from ..types.enums import LayoutDirection

if TYPE_CHECKING:
    from .base import BaseGraph

#: Number of barycenter passes that reorder each layer to cut edge crossings.
ORDER_SWEEPS = 4


@dataclass(frozen=True)
class ArrangeGaps:
    """The space ``arrange_layout`` leaves between cards, in canvas units.

    Example::

        arrange_layout(graph, ArrangeScope.ALL)                                # the defaults
        arrange_layout(graph, ArrangeScope.ALL, gaps=ArrangeGaps.from_settings())  # the user's
        arrange_layout(graph, ArrangeScope.ALL, gaps=ArrangeGaps(rank=200))    # wide columns
    """

    rank: float = 200.0
    """Between two layers, along the flow."""
    cross: float = 100.0
    """Between two cards of one layer, across the flow."""
    band: float = 100.0
    """Between two unconnected parts of the graph, across the flow (``ArrangeScope.ALL``)."""

    @classmethod
    def from_settings(cls) -> "ArrangeGaps":
        """Return the gaps set in ``ArrangeSettings``, or the defaults when settings are not up."""
        try:
            from .arrange_settings import ArrangeSettings

            settings = ArrangeSettings()
            return cls(settings.rank_gap, settings.cross_gap, settings.band_gap)
        except Exception:
            return cls()


#: The gaps ``arrange_layout`` uses when given none.
DEFAULT_GAPS = ArrangeGaps()


class ArrangeScope(str, Enum):
    """Which nodes an arrange or a flow selection acts on.

    ``FLOW`` is every node connected to the start node by any path of edges, whichever way
    they point. ``DOWNSTREAM`` and ``UPSTREAM`` follow edges forward or backward from it.
    ``ALL`` is the whole graph and has no start node.
    """

    FLOW = "flow"
    DOWNSTREAM = "downstream"
    UPSTREAM = "upstream"
    ALL = "all"


def connected_nodes(graph: "BaseGraph", node_id: Optional[str], scope: ArrangeScope | str) -> set[str]:
    """Return the ids of the nodes ``scope`` covers from ``node_id``, the start node included.

    Every edge counts, control and data alike; a cycle is walked once. ``ALL`` ignores
    ``node_id``. An unknown ``node_id`` gives an empty set.

    Raises:
        ValueError: If ``scope`` names no ``ArrangeScope`` member; a plain string such as
            ``"flow"`` is accepted.

    Example::

        # a -> b -> c, d -> b
        connected_nodes(graph, "b", ArrangeScope.DOWNSTREAM)   # {"b", "c"}
        connected_nodes(graph, "b", ArrangeScope.UPSTREAM)     # {"a", "b", "d"}
        connected_nodes(graph, "a", ArrangeScope.FLOW)         # {"a", "b", "c", "d"}
    """
    scope = ArrangeScope(scope)
    nodes = _nodes(graph)
    if scope is ArrangeScope.ALL:
        return set(nodes)
    if node_id not in nodes:
        return set()
    succ, pred = _adjacency(graph, nodes)
    if scope is ArrangeScope.DOWNSTREAM:
        steps = [succ]
    elif scope is ArrangeScope.UPSTREAM:
        steps = [pred]
    else:
        steps = [succ, pred]
    found = {node_id}
    queue = deque([node_id])
    while queue:
        current = queue.popleft()
        for step in steps:
            for neighbour in step[current]:
                if neighbour not in found:
                    found.add(neighbour)
                    queue.append(neighbour)
    return found


def arranged_nodes(
    graph: "BaseGraph", scope: ArrangeScope | str, start: str | Collection[str] | None
) -> set[str]:
    """Return the ids of the nodes ``arrange_layout`` covers for ``scope`` and ``start``.

    Several start nodes are allowed for ``FLOW`` only: the result is the union of their flows.
    Unknown ids contribute nothing.

    Raises:
        ValueError: If ``scope`` names no ``ArrangeScope`` member, or if several start nodes
            are given for ``DOWNSTREAM`` or ``UPSTREAM``.
    """
    scope = ArrangeScope(scope)
    starts = _starts(start)
    if len(starts) > 1 and scope in (ArrangeScope.DOWNSTREAM, ArrangeScope.UPSTREAM):
        raise ValueError(f"Arrange {scope.value} takes one start node, got {len(starts)}.")
    if scope is ArrangeScope.ALL:
        return connected_nodes(graph, None, scope)
    found: set[str] = set()
    for node_id in starts:
        if node_id not in found:
            found |= connected_nodes(graph, node_id, scope)
    return found


def arrange_layout(
    graph: "BaseGraph",
    scope: ArrangeScope | str,
    start: str | Collection[str] | None = None,
    gaps: ArrangeGaps = DEFAULT_GAPS,
) -> dict[str, dict[str, float]]:
    """Return the patch positions that lay out the nodes ``scope`` covers from ``start``.

    ``scope`` may be a plain string such as ``"downstream"``. ``start`` is the start node's id;
    ``FLOW`` also takes several, covering every flow they touch. ``gaps`` sets the space
    between cards; pass ``ArrangeGaps.from_settings()`` for the user's.

    The nodes are placed in layers along the graph's ``layout_direction``, so edges run from
    one layer to a later one; each layer is ordered to reduce crossings. A single start node
    keeps its position and the layout is placed around it. ``ALL`` and several start nodes
    have no anchor: each unconnected part becomes a band of its own, and the whole stays
    centred where the moving nodes were.

    A single start node and locked nodes are left out of the result — they never move. Nodes
    outside the set are not considered, so the layout may overlap them. The result is the same
    on every call for the same graph.

    Returns:
        Node id to ``{"x": ..., "y": ...}``, ready for ``Editor.move_nodes_to``. Empty when
        nothing would move, or when ``start`` is unknown or missing for a scope that needs it.

    Raises:
        ValueError: As ``arranged_nodes``.

    Example::

        positions = arrange_layout(graph, ArrangeScope.DOWNSTREAM, "n1")
        editor.move_nodes_to(positions)   # one undo step; n1 stays put

        arrange_layout(graph, ArrangeScope.FLOW, ["n1", "n7"])   # both flows, centred in place
        arrange_layout(graph, ArrangeScope.ALL)                  # the whole graph
    """
    scope = ArrangeScope(scope)
    members = arranged_nodes(graph, scope, start)
    if not members:
        return {}
    starts = _starts(start)
    anchor = starts[0] if scope is not ArrangeScope.ALL and len(starts) == 1 else None
    order = [n for n in _nodes(graph) if n in members]
    succ, pred = _adjacency(graph, members)
    direction = _graph_direction(graph)
    sizes = {n: _size(graph, n) for n in order}

    if anchor is None:
        components = _components(order, succ, pred)
    else:
        components = [order]

    abstract: dict[str, tuple[float, float]] = {}
    cross_offset = 0.0
    for component in components:
        ranks = _ranks(component, succ, pred, anchor, upstream=scope is ArrangeScope.UPSTREAM)
        layers = _ordered_layers(component, ranks, succ, pred)
        placed, span = _coordinates(layers, sizes, direction, gaps)
        for n, (a, c) in placed.items():
            abstract[n] = (a, c + cross_offset - span[0])
        cross_offset += span[1] - span[0] + gaps.band

    canvas = {n: _to_canvas(a, c, sizes[n], direction) for n, (a, c) in abstract.items()}
    current = {n: _position(graph, n) for n in order}
    fixed = {n for n in order if _locked(graph, n)}
    if anchor is not None:
        fixed.add(anchor)
        dx = current[anchor][0] - canvas[anchor][0]
        dy = current[anchor][1] - canvas[anchor][1]
    else:
        moving = [n for n in order if n not in fixed]
        if not moving:
            return {}
        dx = sum(current[n][0] - canvas[n][0] for n in moving) / len(moving)
        dy = sum(current[n][1] - canvas[n][1] for n in moving) / len(moving)
    return {n: {"x": canvas[n][0] + dx, "y": canvas[n][1] + dy} for n in order if n not in fixed}


def rotated_positions(
    graph: "BaseGraph", node_ids: Collection[str], clockwise: bool
) -> dict[str, dict[str, float]]:
    """Return the patch positions that turn the layout of ``node_ids`` a quarter turn.

    Each card's centre turns 90 degrees about the centre of all the cards, so the group stays
    where it was; the cards themselves keep their size. Locked nodes turn with the rest. Use it
    after changing a graph's layout direction, which moves no node: L2R turns into T2B
    clockwise, and into B2T counter-clockwise.

    Returns:
        Node id to ``{"x": ..., "y": ...}``, ready for ``Editor.move_nodes_to``. Empty for
        fewer than two known nodes, since one card turns in place.

    Example::

        editor.move_nodes_to(rotated_positions(graph, ["a", "b", "c"], clockwise=True))
    """
    known = [n for n in _starts(node_ids) if n in graph.node_wrappers and graph.node_wrappers[n].node]
    if len(known) < 2:
        return {}
    centres = {}
    for n in known:
        (x, y), (w, h) = _position(graph, n), _size(graph, n)
        centres[n] = (x + w / 2, y + h / 2)
    cx = sum(x for x, _ in centres.values()) / len(centres)
    cy = sum(y for _, y in centres.values()) / len(centres)
    positions = {}
    for n, (x, y) in centres.items():
        dx, dy = x - cx, y - cy
        # Canvas y points down, so clockwise on screen takes right to down.
        tx, ty = (cx - dy, cy + dx) if clockwise else (cx + dy, cy - dx)
        w, h = _size(graph, n)
        positions[n] = {"x": tx - w / 2, "y": ty - h / 2}
    return positions


# =============================================================================
# GRAPH READING
# =============================================================================


def _starts(start: str | Collection[str] | None) -> list[str]:
    """``start`` as a list of distinct ids, in the order given."""
    if start is None:
        return []
    if isinstance(start, str):
        return [start]
    return list(dict.fromkeys(start))


def _nodes(graph: "BaseGraph") -> list[str]:
    """The ids of the graph's nodes, in graph order."""
    return [node_id for node_id, wrapper in graph.node_wrappers.items() if wrapper.node is not None]


def _adjacency(graph: "BaseGraph", members) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Successors and predecessors among ``members``, one entry per neighbour, in edge order."""
    succ: dict[str, list[str]] = {n: [] for n in members}
    pred: dict[str, list[str]] = {n: [] for n in members}
    for edge in graph.edge_wrappers.values():
        source, sink = edge.source_node_id, edge.sink_node_id
        if source == sink or source not in succ or sink not in succ or sink in succ[source]:
            continue
        succ[source].append(sink)
        pred[sink].append(source)
    return succ, pred


def _graph_direction(graph: "BaseGraph") -> LayoutDirection:
    try:
        return LayoutDirection.coerce(graph.props.layout_direction)
    except Exception:
        return LayoutDirection.LEFT_TO_RIGHT


def _size(graph: "BaseGraph", node_id: str) -> tuple[float, float]:
    props = graph.node_wrappers[node_id].node.props
    return float(getattr(props, PATCH.width)), float(getattr(props, PATCH.height))


def _position(graph: "BaseGraph", node_id: str) -> tuple[float, float]:
    props = graph.node_wrappers[node_id].node.props
    return float(getattr(props, PATCH.x)), float(getattr(props, PATCH.y))


def _locked(graph: "BaseGraph", node_id: str) -> bool:
    return bool(graph.node_wrappers[node_id].node.props.locked)


# =============================================================================
# LAYERING
# =============================================================================


def _components(order: list[str], succ, pred) -> list[list[str]]:
    """The weakly connected components of ``order``, each in graph order."""
    seen: set[str] = set()
    components = []
    for start in order:
        if start in seen:
            continue
        found = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbour in (*succ[current], *pred[current]):
                if neighbour not in found:
                    found.add(neighbour)
                    queue.append(neighbour)
        seen |= found
        components.append([n for n in order if n in found])
    return components


def _ranks(component: list[str], succ, pred, anchor: Optional[str], upstream: bool) -> dict[str, int]:
    """The layer of each node: every edge that is not part of a cycle points to a later layer.

    The walk that finds the cycles starts at the anchor (backward for ``upstream``), else at the
    nodes with no predecessor; the edge that closes a cycle is ignored. Each node then sits one
    layer after its furthest predecessor, and a node with no predecessor is pulled up to just
    before its nearest successor, so a node feeding one consumer sits next to it.
    """
    forward, backward = (pred, succ) if upstream else (succ, pred)
    if anchor is not None:
        roots = [anchor]
    else:
        roots = [n for n in component if not backward[n]]
    back_edges = _back_edges(component, forward, roots)

    def ahead(n: str) -> list[str]:
        return [m for m in forward[n] if (n, m) not in back_edges]

    def behind(n: str) -> list[str]:
        return [m for m in backward[n] if (m, n) not in back_edges]

    topo = _topological(component, ahead, behind)
    rank: dict[str, int] = {}
    for n in topo:
        rank[n] = max((rank[m] + 1 for m in behind(n)), default=0)
    for n in reversed(topo):
        if n != anchor and not behind(n) and ahead(n):
            rank[n] = min(rank[m] for m in ahead(n)) - 1
    if upstream:
        rank = {n: -r for n, r in rank.items()}
    low = min(rank.values())
    return {n: r - low for n, r in rank.items()}


def _back_edges(component: list[str], forward, roots: list[str]) -> set[tuple[str, str]]:
    """The edges that close a cycle, found by a depth-first walk from ``roots`` then the rest."""
    state: dict[str, int] = {}  # 1 = on the walk's path, 2 = done
    back: set[tuple[str, str]] = set()
    for root in (*roots, *component):
        if root in state:
            continue
        state[root] = 1
        stack = [(root, iter(forward[root]))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                state[node] = 2
                stack.pop()
            elif child not in state:
                state[child] = 1
                stack.append((child, iter(forward[child])))
            elif state[child] == 1:
                back.add((node, child))
    return back


def _topological(component: list[str], ahead, behind) -> list[str]:
    """``component`` in an order where each node comes after everything ``behind`` it."""
    waiting = {n: len(behind(n)) for n in component}
    queue = deque(n for n in component if waiting[n] == 0)
    topo = []
    while queue:
        n = queue.popleft()
        topo.append(n)
        for m in ahead(n):
            waiting[m] -= 1
            if waiting[m] == 0:
                queue.append(m)
    return topo


def _ordered_layers(component: list[str], ranks: dict[str, int], succ, pred) -> list[list[str]]:
    """The nodes of each layer, ordered to reduce crossings.

    Starts in graph order, then alternately sorts each layer by the mean position of its
    neighbours in the layers before it, then after it. A node with no such neighbour keeps its
    place. Ties keep the previous order, so the result is the same on every call.
    """
    layers: list[list[str]] = [[] for _ in range(max(ranks.values()) + 1)]
    for n in component:
        layers[ranks[n]].append(n)
    for sweep in range(ORDER_SWEEPS):
        downward = sweep % 2 == 0
        indices = range(1, len(layers)) if downward else range(len(layers) - 2, -1, -1)
        for i in indices:
            place = {n: (k + 0.5) / len(layer) for layer in layers for k, n in enumerate(layer)}
            keys = []
            for k, n in enumerate(layers[i]):
                near = [
                    place[m] for m in (*pred[n], *succ[n]) if (ranks[m] < i if downward else ranks[m] > i)
                ]
                keys.append((sum(near) / len(near) if near else place[n], k, n))
            layers[i] = [n for _, _, n in sorted(keys)]
    return layers


# =============================================================================
# COORDINATES
# =============================================================================


def _extents(size: tuple[float, float], direction: LayoutDirection) -> tuple[float, float]:
    """A card's ``(along, across)`` extent for ``direction``."""
    width, height = size
    return (height, width) if direction.is_vertical else (width, height)


def _coordinates(
    layers: list[list[str]],
    sizes: dict[str, tuple[float, float]],
    direction: LayoutDirection,
    gaps: ArrangeGaps,
) -> tuple[dict[str, tuple[float, float]], tuple[float, float]]:
    """Each node's ``(along, across)`` start corner, and the cross-axis span of the whole.

    Layers advance along the flow by their widest card plus the rank gap; within a layer the
    cards stack across the flow, centred on the flow's axis.
    """
    placed: dict[str, tuple[float, float]] = {}
    along = 0.0
    low = high = 0.0
    for layer in layers:
        extents = [_extents(sizes[n], direction) for n in layer]
        total = sum(e[1] for e in extents) + gaps.cross * (len(layer) - 1)
        across = -total / 2
        low, high = min(low, across), max(high, across + total)
        for n, (_, cross) in zip(layer, extents, strict=True):
            placed[n] = (along, across)
            across += cross + gaps.cross
        along += max(e[0] for e in extents) + gaps.rank
    return placed, (low, high)


def _to_canvas(
    along: float, across: float, size: tuple[float, float], direction: LayoutDirection
) -> tuple[float, float]:
    """The top-left canvas corner of a card placed at ``(along, across)``.

    A flow running left or up is mirrored, using the card's own extent so its far edge lands
    where its near edge would have.
    """
    extent = _extents(size, direction)[0]
    dx, dy = direction.outlet_vector
    if direction.is_vertical:
        return across, along if dy > 0 else -(along + extent)
    return (along if dx > 0 else -(along + extent)), across
