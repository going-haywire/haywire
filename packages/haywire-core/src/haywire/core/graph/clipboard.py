# packages/haywire-core/src/haywire/core/graph/clipboard.py
"""
Pure clipboard-payload builder for graph copy/paste.

This module is intentionally free of NiceGUI and I/O: it turns a selection of
nodes/edges into a serializable dict (the *clipboard payload*) and validates
that an arbitrary object is a haywire payload. Transport (OS clipboard) and
mutation (PasteClipboardAction) live elsewhere.

Payload shape — see docs/superpowers/plans/2026-06-01-node-copy-paste.md.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseGraph

CLIPBOARD_FORMAT_VERSION = 1


def build_clipboard_payload(
    graph: "BaseGraph",
    node_ids: List[str],
    edge_ids: List[str],
    session_id: str,
) -> Dict[str, Any]:
    """Serialize a slice of ``graph`` (selected nodes + edges) into a payload.

    Only edges whose *both* endpoints are in ``node_ids`` are included
    (the both-endpoints rule); boundary-crossing edges are dropped so a
    paste is always self-consistent.
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
    """True iff ``obj`` is a clipboard payload this version can paste.

    Requires the discriminator, a matching format_version, and a numeric
    ``source.timestamp`` (the paste-time arbitration relies on it).
    """
    if not (
        isinstance(obj, dict)
        and obj.get("haywire_clipboard") is True
        and obj.get("format_version") == CLIPBOARD_FORMAT_VERSION
    ):
        return False
    source = obj.get("source")
    return isinstance(source, dict) and isinstance(source.get("timestamp"), (int, float))
