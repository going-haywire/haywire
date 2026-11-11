"""Bring the ports a node was saved with to the declaration its class has now.

Three declarations of a node's ports meet when its class changed since the data was
written: the one the data was saved against (*base*), the saved ports themselves, and
the one ``init()`` makes now (*code*). ``merge_ports`` follows the code wherever the
saved ports still say what the base said, keeps what the saved ports changed, and
returns ``None`` where both changed the same thing. See ADR 0078.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Final, Sequence

from ..errors import ErrorSeverity, HaywireException
from ..errors.ledger import get_error_ledger
from ..types.port import _FLOOR

if TYPE_CHECKING:
    from .node_wrapper import NodeWrapper

logger = logging.getLogger(__name__)

_FILE_OWNED: Final = frozenset({"order", "hidden"})
"""Fields of a declared port a saved value always wins on."""
_ABSENT: Final = object()
_SHOWN_CHANGES: Final = 8


@dataclass
class MergedPorts:
    """The outcome of a merge that found no conflict."""

    ports: dict[str, Any]
    """Port specs keyed by port id, saved against the code's declaration."""
    changes: list[str] = field(default_factory=list)
    """What the code changed, as paths: ``ports/gain/label``, ``ports/mix (added)``."""


def _plain(value: Any) -> Any:
    """Return *value* as a graph file would hold it, so a live value compares with a loaded one."""
    return json.loads(json.dumps(value, default=str))


def merge_ports(
    base: dict[str, Any],
    saved: dict[str, Any],
    code: dict[str, Any],
    code_full: dict[str, Any],
    default_value: Callable[[dict[str, Any]], Any],
) -> MergedPorts | None:
    """Return *saved* brought to the declaration *code*, or ``None`` when the two conflict.

    Args:
        base: The declaration *saved* was written against (``NodeData.saved_declaration`` then).
        saved: Port specs keyed by port id, as a node saves them.
        code: The declaration the class makes now (``NodeData.saved_declaration``).
        code_full: The same declaration with every field (``NodeData.declaration``).
        default_value: Returns the value a port built from a declaration entry saves while
            nobody has set it. May raise; the saved value then counts as set.

    A conflict is: one field of a port changed in both *saved* and *code* to different
    values; a port the node retyped or removed itself that the code changed too; a port
    the code retyped that holds anything of its own; a port id the node grew itself that
    the code now declares.
    """
    base, code, code_full = _plain(base), _plain(code), _plain(code_full)
    merged = MergedPorts(ports={})

    for port_id, spec in saved.items():
        was, now = base.get(port_id), code.get(port_id)
        if was is None and now is None:
            merged.ports[port_id] = spec
        elif was is None:
            return None
        elif now is None:
            if _plain(spec.get("recipe")) != was["recipe"]:
                return None
            merged.changes.append(f"ports/{port_id} (removed)")
        elif was == now:
            merged.ports[port_id] = spec
        else:
            port = _merge_port(port_id, was, spec, now, code_full[port_id], default_value, merged.changes)
            if port is None:
                return None
            merged.ports[port_id] = port

    anchor: str | None = None
    for port_id, now in code.items():
        if port_id in saved:
            if port_id in merged.ports:
                anchor = port_id
            continue
        was = base.get(port_id)
        if was is None:
            _insert_after(merged.ports, anchor, port_id, copy.deepcopy(now))
            merged.changes.append(f"ports/{port_id} (added)")
            anchor = port_id
        elif was != now:
            # The node removed the port itself, and the code changed it since.
            return None
    return merged


def _merge_port(
    port_id: str,
    was: dict[str, Any],
    spec: dict[str, Any],
    now: dict[str, Any],
    now_full: dict[str, Any],
    default_value: Callable[[dict[str, Any]], Any],
    changes: list[str],
) -> dict[str, Any] | None:
    """Merge one port both declarations hold and the code changed; ``None`` on a conflict."""
    kwargs = spec.get("kwargs", {})
    plain = _plain(kwargs)
    if _plain(spec.get("recipe")) != was["recipe"]:
        return None

    def untouched_value() -> bool:
        if "field_data" not in spec:
            return True
        try:
            return bool(_plain(spec["field_data"]) == _plain(default_value(copy.deepcopy(was))))
        except Exception:
            logger.debug("Port %s: default of the earlier declaration not built", port_id, exc_info=True)
            return False

    if now["recipe"] != was["recipe"]:
        own = [name for name, value in plain.items() if value != was["kwargs"].get(name, _ABSENT)]
        if own or not untouched_value():
            return None
        changes.append(f"ports/{port_id}/recipe")
        return copy.deepcopy(now)

    result = dict(kwargs)
    names = sorted(set(was["kwargs"]) | set(now["kwargs"]))
    for name in names:
        before, after = was["kwargs"].get(name, _ABSENT), now["kwargs"].get(name, _ABSENT)
        if before == after:
            continue
        changes.append(f"ports/{port_id}/{name}")
        if name not in plain:
            continue
        mine = plain[name]
        if (name in _FLOOR and mine == before) or mine == now_full["kwargs"].get(name, _ABSENT):
            del result[name]
        elif name not in _FILE_OWNED:
            return None

    merged = {**spec, "kwargs": result}
    if "default" in names and was["kwargs"].get("default", _ABSENT) != now["kwargs"].get("default", _ABSENT):
        if "field_data" in merged and untouched_value():
            del merged["field_data"]
    return merged


def _insert_after(ports: dict[str, Any], anchor: str | None, port_id: str, spec: dict[str, Any]) -> None:
    """Put *spec* into *ports* right after the port *anchor*, or first when *anchor* is ``None``."""
    items = list(ports.items())
    at = 0 if anchor is None else [key for key, _ in items].index(anchor) + 1
    items.insert(at, (port_id, spec))
    ports.clear()
    ports.update(items)


def report_merge(wrapper: "NodeWrapper", *, operation: str, changes: Sequence[str]) -> None:
    """Record a ledger note that *wrapper*'s node took over what its code changed. Never raises.

    Args:
        operation: ``"Load graph"`` or ``"Hot reload"``.
        changes: What the code changed, as ``MergedPorts.changes`` lists it.
    """
    try:
        graph = wrapper.graph
        message = f"{wrapper.node.display_label} '{wrapper.node_id}' follows its changed code"
        entry = HaywireException.create(message, severity=ErrorSeverity.INFO, operation=operation)
        entry.enrich(graph_id=graph.graph_id, node_id=wrapper.node_id)
        shown = ", ".join(changes[:_SHOWN_CHANGES])
        entry.details["changed"] = shown + (
            f" (+{len(changes) - _SHOWN_CHANGES} more)" if len(changes) > _SHOWN_CHANGES else ""
        )
        # Recorded without the console report an error gets: nothing went wrong.
        get_error_ledger().record(entry)
        logger.info("%s: %s", message, entry.details["changed"])
    except Exception:
        logger.debug("No ledger entry for the merge of %s", wrapper.node_id, exc_info=True)
