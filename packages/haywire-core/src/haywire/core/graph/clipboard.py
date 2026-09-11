# packages/haywire-core/src/haywire/core/graph/clipboard.py
"""Build and recognise the clipboard payload for graph copy/paste.

Pure: no NiceGUI, no I/O. Transport (the OS clipboard) and mutation
(``PasteClipboardAction``) live elsewhere.

Payload shape — see docs/superpowers/plans/2026-06-01-node-copy-paste.md.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseGraph

#: A payload carries whole serialized nodes and is matched on this exact value.
#: Payloads are transient and never migrated, so one left on the system
#: clipboard by another version is refused.
CLIPBOARD_FORMAT_VERSION = 2


def build_clipboard_payload(
    graph: "BaseGraph",
    node_ids: List[str],
    edge_ids: List[str],
    session_id: str,
) -> Dict[str, Any]:
    """Serialize the given nodes and edges of ``graph`` into a clipboard payload.

    Only edges with both endpoints in ``node_ids`` are included, so a paste is
    always self-consistent. Ids the graph doesn't know are skipped.

    Returns:
        ``haywire_clipboard``, ``format_version``, ``source`` (``session_id``
        and a ``timestamp`` in epoch seconds), ``bounding_box`` over the node
        positions, and the serialized ``nodes`` and ``edges``.
    """
    selected = set(node_ids)

    nodes: Dict[str, Any] = {}
    positions: list[tuple[float, float]] = []
    for node_id in node_ids:
        wrapper = graph.get_node_wrapper(node_id)
        if wrapper is None:
            continue
        serialized = wrapper.serialize(include_data=True)
        nodes[node_id] = serialized
        pos = serialized.get("position") or [0.0, 0.0]
        positions.append((float(pos[0]), float(pos[1])))

    edges: Dict[str, Any] = {}
    for edge_id in edge_ids:
        edge_wrapper = graph.get_edge_wrapper(edge_id)
        if edge_wrapper is None:
            continue
        edge_dict = edge_wrapper.edge.to_dict()
        if edge_dict["source_node_id"] in selected and edge_dict["sink_node_id"] in selected:
            edges[edge_id] = edge_dict

    if positions:
        bounding_box = {
            "min_x": min(p[0] for p in positions),
            "min_y": min(p[1] for p in positions),
            "max_x": max(p[0] for p in positions),
            "max_y": max(p[1] for p in positions),
        }
    else:
        bounding_box = {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0}

    return {
        "haywire_clipboard": True,
        "format_version": CLIPBOARD_FORMAT_VERSION,
        "source": {"session_id": session_id, "timestamp": time.time()},
        "bounding_box": bounding_box,
        "nodes": nodes,
        "edges": edges,
    }


def is_haywire_payload(obj: Any) -> bool:
    """Return whether ``obj`` is a clipboard payload this version can paste.

    Requires the ``haywire_clipboard`` marker, a ``format_version`` equal to
    ``CLIPBOARD_FORMAT_VERSION``, and a numeric ``source.timestamp``.
    """
    if not (
        isinstance(obj, dict)
        and obj.get("haywire_clipboard") is True
        and obj.get("format_version") == CLIPBOARD_FORMAT_VERSION
    ):
        return False
    source = obj.get("source")
    return isinstance(source, dict) and isinstance(source.get("timestamp"), (int, float))
