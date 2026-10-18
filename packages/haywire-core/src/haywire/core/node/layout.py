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
        PATCH.z                                  # "z", the stacking order
        props.set_position((10.0, 20.0), PATCH)  # writes props.posX / props.posY
    """

    name: str
    x: str
    y: str
    width: str
    height: str
    size_adapt: str
    z: str
    member: str | None = None
    origin: float = 0.0
    stage: bool = False

    def includes(self, props: Any) -> bool:
        """Whether a node with these props is laid out on this channel.

        A channel with no ``member`` includes every node; otherwise the node's ``member``
        field must be truthy.

        Example::

            STAGE.includes(node.props)   # node.props.on_stage
        """
        return self.member is None or bool(getattr(props, self.member))

    def to_canvas(self, x: float, y: float) -> tuple[float, float]:
        """Return the canvas position of a channel position: ``origin`` added to both axes."""
        return x + self.origin, y + self.origin

    def from_canvas(self, x: float, y: float) -> tuple[float, float]:
        """Return the channel position of a canvas position: ``origin`` taken from both axes."""
        return x - self.origin, y - self.origin


PATCH = LayoutChannel(
    name="patch", x="posX", y="posY", width="width", height="height", size_adapt="size_adapt", z="z"
)

STAGE = LayoutChannel(
    name="stage",
    x="stage_x",
    y="stage_y",
    width="stage_width",
    height="stage_height",
    size_adapt="stage_size_adapt",
    z="stage_z",
    member="on_stage",
    origin=200.0,
    stage=True,
)

#: Every layout channel, patch first.
CHANNELS = (PATCH, STAGE)


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


def with_z(node_data: Mapping[str, Any] | None, z: int, channel: LayoutChannel = PATCH) -> dict[str, Any]:
    """Return a copy of ``node_data`` with the channel's stacking field set to ``z``.

    ``node_data`` is not mutated; ``None`` is treated as empty. Other props values are kept.

    Example::

        node_data = with_z(saved["node_data"], 4)            # patch stacking order
        node_data = with_z(node_data, 2, STAGE)              # stage stacking order
    """
    result = dict(node_data or {})
    props = dict(result.get("props") or {})
    values = dict(props.get("values") or {})
    values[channel.z] = z
    props["values"] = values
    result["props"] = props
    return result


def with_stage_placement(
    node_data: Mapping[str, Any] | None,
    x: float,
    y: float,
    patch_xy: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Return a copy of ``node_data`` that puts the node on the stage at stage position ``(x, y)``.

    The node is on stage with ``stage_size_adapt`` ``"auto"``. Its patch position is ``patch_xy``,
    or the same numbers as the stage position when that is ``None``. ``node_data`` is not
    mutated; other props values are kept.

    Example::

        node_data = with_stage_placement(None, 40.0, 60.0)                  # stage_x == posX == 40.0
        node_data = with_stage_placement(None, 40.0, 60.0, (900.0, 700.0))  # posX == 900.0
    """
    px, py = (x, y) if patch_xy is None else patch_xy
    result = with_position(with_position(node_data, px, py, PATCH), x, y, STAGE)
    values = result["props"]["values"]
    values["on_stage"] = True
    values[STAGE.size_adapt] = "auto"
    return result


def layout_position_of(node: Mapping[str, Any], channel: LayoutChannel = PATCH) -> tuple[float, float]:
    """Return the ``(x, y)`` a serialized node has on ``channel``.

    On a channel with a ``member`` field, a node that is not a member reads its patch position.

    Example::

        layout_position_of(payload_node, STAGE)   # stage position if on stage, else posX/posY
    """
    if channel.member is not None and not _values(node.get("node_data")).get(channel.member):
        return position_of(node, PATCH)
    return position_of(node, channel)
