"""The props fields a canvas lays a node out with, and helpers to read them.

A ``LayoutChannel`` names those fields; ``PATCH`` is the channel of the patch
canvas. A serialized node stores its layout under
``node["node_data"]["props"]["values"]``, and a value equal to its default is
omitted, so a missing field reads as ``0.0``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LayoutChannel:
    """Names the ``NodeProperties`` fields that hold one canvas's layout.

    Example::

        PATCH.x                                  # "posX"
        props.set_position((10.0, 20.0), PATCH)  # writes props.posX / props.posY
    """

    name: str
    x: str
    y: str
    width: str
    height: str
    size_adapt: str


PATCH = LayoutChannel(
    name="patch", x="posX", y="posY", width="width", height="height", size_adapt="size_adapt"
)


def _values(node_data: Mapping[str, Any] | None) -> Mapping[str, Any]:
    props = (node_data or {}).get("props") or {}
    return props.get("values") or {}


def position_of(node: Mapping[str, Any], channel: LayoutChannel = PATCH) -> tuple[float, float]:
    """Return the ``(x, y)`` of a serialized node, as ``NodeWrapper.serialize`` returns it.

    A missing ``node_data``, ``props``, ``values`` or field reads as ``0.0``.

    Example::

        position_of(wrapper.serialize())             # position on the patch
        position_of({"node_id": "n1"})               # (0.0, 0.0)
    """
    values = _values(node.get("node_data"))
    return float(values.get(channel.x, 0.0)), float(values.get(channel.y, 0.0))


def with_position(
    node_data: Mapping[str, Any] | None, x: float, y: float, channel: LayoutChannel = PATCH
) -> dict[str, Any]:
    """Return a copy of ``node_data`` with the channel's position fields set.

    ``node_data`` is not mutated; ``None`` is treated as empty. Other props values and the
    rest of ``node_data`` are kept.

    Example::

        node_data = with_position(saved["node_data"], 120.5, 40.0)
    """
    result = dict(node_data or {})
    props = dict(result.get("props") or {})
    values = dict(props.get("values") or {})
    values[channel.x] = x
    values[channel.y] = y
    props["values"] = values
    result["props"] = props
    return result
