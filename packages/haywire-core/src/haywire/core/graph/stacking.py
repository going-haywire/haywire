"""The order a view paints its nodes in, and the verbs that change it.

Each layout channel has its own stacking field (``PATCH.z``, ``STAGE.z``). A view paints its
member nodes bottom to top by ``(z, position in the graph)``, so nodes that share a z paint in
the order they were added to the graph.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from enum import Enum
from typing import TYPE_CHECKING

from ..node.layout import LayoutChannel

if TYPE_CHECKING:
    from .base import BaseGraph


class Restack(str, Enum):
    """A change to the stacking order of a set of nodes in one view.

    ``FRONT`` and ``BACK`` move the nodes above or below every other node. ``FORWARD`` and
    ``BACKWARD`` move each node one step, past the next node above or below it that is not
    moving too. The moving nodes keep their order among themselves.
    """

    FRONT = "front"
    BACK = "back"
    FORWARD = "forward"
    BACKWARD = "backward"


def stacking_order(graph: "BaseGraph", channel: LayoutChannel) -> list[str]:
    """Return the ids of the nodes ``channel`` includes, in paint order, bottom first.

    Example::

        stacking_order(graph, PATCH)   # ["n1", "n3", "n2"]: n2 paints on top
        stacking_order(graph, STAGE)   # only on-stage nodes
    """
    members = [
        (getattr(wrapper.node.props, channel.z), index, node_id)
        for index, (node_id, wrapper) in enumerate(graph.node_wrappers.items())
        if wrapper.node is not None and channel.includes(wrapper.node.props)
    ]
    return [node_id for _, _, node_id in sorted(members)]


def restacked(
    graph: "BaseGraph", node_ids: Iterable[str], how: Restack, channel: LayoutChannel
) -> dict[str, int]:
    """Return the new stacking value of each node that ``how`` changes, applied to ``node_ids``.

    The new order is written as ranks: the node at paint position ``i`` gets ``i``. Only nodes
    whose value differs from their rank are returned. Ids the graph does not know, or that
    ``channel`` does not include, are ignored. The result is empty when the paint order does not
    change, even if the stored values are not ranks yet.

    Raises:
        ValueError: If ``how`` names no ``Restack`` member; a plain string such as ``"front"``
            is accepted.

    Example::

        # a, b, c, d all at 0, painted in that order
        restacked(graph, ["a"], Restack.FRONT, PATCH)      # {"c": 1, "d": 2, "a": 3}; b stays 0
        restacked(graph, ["a"], Restack.FORWARD, PATCH)    # {"a": 1, "c": 2, "d": 3}; order b, a, c, d
    """
    how = Restack(how)
    before = stacking_order(graph, channel)
    order = list(before)
    moving = set(node_ids) & set(order)
    if not moving:
        return {}
    if how is Restack.FRONT:
        order = [n for n in order if n not in moving] + [n for n in order if n in moving]
    elif how is Restack.BACK:
        order = [n for n in order if n in moving] + [n for n in order if n not in moving]
    elif how is Restack.FORWARD:
        for i in range(len(order) - 2, -1, -1):
            if order[i] in moving and order[i + 1] not in moving:
                order[i], order[i + 1] = order[i + 1], order[i]
    else:
        for i in range(1, len(order)):
            if order[i] in moving and order[i - 1] not in moving:
                order[i], order[i - 1] = order[i - 1], order[i]
    if order == before:
        return {}

    changes: dict[str, int] = {}
    for rank, node_id in enumerate(order):
        if getattr(graph.node_wrappers[node_id].node.props, channel.z) != rank:
            changes[node_id] = rank
    return changes


def top_z(graph: "BaseGraph", channel: LayoutChannel, exclude: Collection[str] = ()) -> int:
    """Return the stacking value that puts a node above every node ``channel`` includes.

    That is the highest value among the included nodes not in ``exclude``, plus one, or ``0``
    when there are none.

    Example::

        top_z(graph, PATCH)                      # 4 when the highest z is 3
        top_z(graph, STAGE, exclude={"n7"})      # ignoring n7 itself
    """
    values = [
        getattr(wrapper.node.props, channel.z)
        for node_id, wrapper in graph.node_wrappers.items()
        if node_id not in exclude and wrapper.node is not None and channel.includes(wrapper.node.props)
    ]
    return max(values) + 1 if values else 0
