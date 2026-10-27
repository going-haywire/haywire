"""The previous setup a node keeps after a hot reload rebuilt it from new code.

A node holds its pre-reload data until the user applies or dismisses it. The data
travels inside the node's own ``node_data`` under ``PREVIOUS_SETUP_KEY``, so a
saved file and an undo snapshot carry it; copies drop it (``strip_previous_setups``).
See ADR 0062.
"""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Any, Final, Sequence

from ..errors import ErrorSeverity, HaywireException

if TYPE_CHECKING:
    from .node_wrapper import NodeWrapper

logger = logging.getLogger(__name__)

PREVIOUS_SETUP_KEY: Final = "previous_setup"
_SHOWN_PATHS: Final = 8
PREVIOUS_SETUP_WARNING: Final = (
    "Rebuilt from its changed code with default settings. The earlier settings were kept."
)


def strip_previous_setups(document: dict[str, Any]) -> None:
    """Remove every node's previous setup from a graph document, interiors included.

    Args:
        document: A graph or Subgraph document as ``to_dict`` returns it, or a
            clipboard payload: ``nodes`` map to serialized wrappers, ``subgraphs``
            to documents of the same shape. Changed in place.
    """
    for node in document.get("nodes", {}).values():
        node_data = node.get("node_data")
        if isinstance(node_data, dict):
            node_data.pop(PREVIOUS_SETUP_KEY, None)
    for subgraph in document.get("subgraphs", {}).values():
        if isinstance(subgraph, dict):
            strip_previous_setups(subgraph)


def setup_to_apply(wrapper: "NodeWrapper") -> dict[str, Any] | None:
    """Return the node data that applies *wrapper*'s previous setup, or ``None`` when it holds none.

    The previous setup with the node's arrangement as it is now (position, stacking
    order, place on stage), so Apply restores the setup without moving the node.
    """
    from .node_wrapper import _CARRIED_ARRANGEMENT

    held = wrapper.previous_setup
    if held is None:
        return None
    data = copy.deepcopy(held)
    current = wrapper.serialize()["node_data"]
    arrangement = ("posX", "posY", *_CARRIED_ARRANGEMENT)
    for holder, live in ((data, current), (data.get("settings", {}), current.get("settings", {}))):
        values = holder.setdefault("props", {}).setdefault("values", {})
        live_values = live.get("props", {}).get("values", {})
        for name in arrangement:
            if name in live_values:
                values[name] = copy.deepcopy(live_values[name])
            else:
                values.pop(name, None)
    return data


_SIZES = (("width", "height", "size_adapt"), ("stage_width", "stage_height", "stage_size_adapt"))


def restorable(node_data: dict[str, Any]) -> dict[str, Any]:
    """Return *node_data* reduced to what Apply restores, for telling a changed setup from an unchanged one.

    Left out: ``identity`` and ``library`` (they describe the class), the node's
    arrangement (Apply keeps it), and a size on an axis whose ``size_adapt`` is
    auto (the canvas measures it). The input is not changed.
    """
    from .node_wrapper import _CARRIED_ARRANGEMENT

    data = {key: value for key, value in node_data.items() if key not in ("identity", "library")}
    data = copy.deepcopy(data)
    for holder in (data, data.get("settings", {})):
        values = holder.get("props", {}).get("values")
        if not isinstance(values, dict):
            continue
        for name in ("posX", "posY", *_CARRIED_ARRANGEMENT):
            values.pop(name, None)
        for width, height, adapt in _SIZES:
            mode = values.get(adapt, "auto")
            if mode not in ("manual", "manual_width"):
                values.pop(width, None)
            if mode not in ("manual", "manual_height"):
                values.pop(height, None)
    return data


def differing_paths(before: Any, after: Any, path: str = "") -> list[str]:
    """Return the paths at which two node data trees differ, slash-joined: ``ports/message/field_data``."""
    if isinstance(before, dict) and isinstance(after, dict):
        found: list[str] = []
        for key in sorted(set(before) | set(after), key=str):
            child = f"{path}/{key}" if path else str(key)
            if key not in before or key not in after:
                found.append(child)
            else:
                found.extend(differing_paths(before[key], after[key], child))
        return found
    return [] if before == after else [path]


def report_previous_setup(wrapper: "NodeWrapper", *, operation: str, differs: Sequence[str] = ()) -> None:
    """Record a ledger warning that *wrapper*'s node holds a previous setup. Never raises.

    Args:
        operation: ``"Hot reload"`` when the reload just kept it, or the operation
            that found it held (``"Load graph"``).
        differs: Where the previous setup differs from the rebuilt node, as
            ``differing_paths`` returns them; shown in the entry's details.
    """
    try:
        graph = wrapper.graph
        verb = "kept its previous setup" if operation == "Hot reload" else "holds a previous setup"
        message = f"{wrapper.node.display_label} '{wrapper.node_id}' {verb}{_where(graph)}"
        entry = HaywireException.create(message, severity=ErrorSeverity.WARNING, operation=operation)
        entry.enrich(graph_id=graph.graph_id, node_id=wrapper.node_id)
        if differs:
            shown = ", ".join(differs[:_SHOWN_PATHS])
            entry.details["differs"] = shown + (
                f" (+{len(differs) - _SHOWN_PATHS} more)" if len(differs) > _SHOWN_PATHS else ""
            )
        entry.log()
    except Exception:
        logger.debug("No ledger entry for the previous setup of %s", wrapper.node_id, exc_info=True)


def _where(graph: Any) -> str:
    """`` (inside '<host>')`` for an interior graph whose host node is known, else empty."""
    host_of = getattr(graph, "graph_node_wrapper", None)
    host = host_of() if callable(host_of) else None
    return f" (inside '{host.node.display_label}')" if host is not None else ""
