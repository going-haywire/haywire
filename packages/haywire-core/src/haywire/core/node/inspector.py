"""Read-only schema introspection over a single live BaseNode instance.

Answers "what ports/settings does this node declare" from an already-built
instance. Does NOT construct nodes and does NOT read live state (values,
links, promotion) — that overlay belongs to callers that hold a NodeWrapper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from haywire.core.node.base import BaseNode


@dataclass(frozen=True)
class PortInfo:
    id: str
    direction: str
    label: str
    description: str
    flow_type: str
    data_type: str | None
    hidden: bool
    deprecation: str


@dataclass(frozen=True)
class SettingInfo:
    name: str
    bag: str
    label: str
    description: str
    category: str
    default: Any
    type_name: str | None
    validator_name: str | None
    validator_doc: str | None


def _port_direction(port: Any) -> str:
    """Three-way port direction: 'inlet', 'outlet', or 'config'.

    A CONFIG port is neither inlet nor outlet — collapsing to a binary
    inlet/else-outlet mislabels every ``as_config(...)`` port as an outlet.
    """
    if port.is_inlet():
        return "inlet"
    if port.is_outlet():
        return "outlet"
    return "config"


def _port_type_key(port: Any) -> str | None:
    """The concrete data-type registry key, or None.

    Defensive: type_cls or its class_identity can be absent on edge cases, so
    miss quietly rather than raise inside a read-only inspector.
    """
    identity = getattr(port.type_cls, "class_identity", None)
    return getattr(identity, "registry_key", None)


def _validator_fields(descriptor: Any) -> tuple[str | None, str | None]:
    validator = getattr(descriptor, "_validator", None)
    if validator is None:
        return None, None
    name = getattr(validator, "__name__", None)
    doc_lines = (getattr(validator, "__doc__", None) or "").strip().splitlines()
    doc = doc_lines[0].strip() if doc_lines else None
    return name, doc


class NodeInstanceInspector:
    """Wrap a built BaseNode and answer its schema questions."""

    def __init__(self, node: "BaseNode") -> None:
        self._node = node

    def ports(self) -> list[PortInfo]:
        rows: list[PortInfo] = []
        for pid, port in self._node.ports.items():
            rows.append(
                PortInfo(
                    id=pid,
                    direction=_port_direction(port),
                    label=port.label or "",
                    description=port.description or "",
                    flow_type=port.flow_type.value,
                    data_type=_port_type_key(port),
                    hidden=bool(port.hidden),
                    deprecation=port.deprecation_warning or "",
                )
            )
        return rows

    def settings(self) -> list[SettingInfo]:
        rows: list[SettingInfo] = []
        for accessor, bag in self._node.list_setting_bags().items():
            for name, descriptor in type(bag)._property_settings().items():
                default = descriptor._default
                resolved = default() if callable(default) else default
                itype = getattr(descriptor, "_type", None)
                vname, vdoc = _validator_fields(descriptor)
                rows.append(
                    SettingInfo(
                        name=name,
                        bag=accessor,
                        label=descriptor._label or "",
                        description=descriptor._description or "",
                        category=descriptor._category or "root",
                        default=resolved,
                        type_name=getattr(itype, "__name__", None),
                        validator_name=vname,
                        validator_doc=vdoc,
                    )
                )
        return rows
