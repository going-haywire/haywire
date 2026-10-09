"""Annotation node — a box of text that links to other annotations with styled arrows.

Lives in the framework-owned builtin library so every graph can carry notes. It
binds its skin by registry-key string on its own props, never importing the skin
class, so the headless execution path never imports nicegui.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from haywire.barn.builtin.types import BOOL, CHOICES, STRING
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import setting
from haywire.core.types import PortOrigin

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.types.port import DataPort


@node(
    label="Annotation",
    description="A box of text for diagrams; links to other annotations with styled arrows",
    menu="annotation",
    search_tags=["note", "comment", "diagram", "arrow", "annotation"],
    node_type=NodeType.CONTROL,
)
class AnnotationNode(BaseNode):
    """A note on the canvas, with arrows to other notes.

    Write the text in the properties panel, or double-click the card to edit it
    in a larger editor. Line breaks are kept.

    Hover the card to show one open pin on each side. Drag from a pin on any side
    to a pin on any side of another annotation: an arrow can leave or arrive at
    each of them, and two pins are joined by one arrow at most. The arrow head sits
    at the end you dropped on; change the heads, colour, dash and width in the
    arrow's edge menu.

    A pin you connect stays, and a new open pin appears after it, so a side can
    hold any number of arrows. A side's pins are kept centred along it. Deleting
    an arrow removes a pin it leaves without one; undoing the delete brings the
    pin back. You can also remove a pin from its pin menu.

    Arrows between annotations are drawn and saved with the graph but never run.
    The node also has a control inlet and outlet that pass control and its
    payload straight through, so a note can sit inside a control chain. They are
    drawn while linked, or always when *Show Control Pins* is on.
    """

    #: The card sides, as named in port ids.
    SIDES = ("top", "right", "bottom", "left")

    # Subclasses the inherited bag, as RerouteNode does (see its comment).
    class props(BaseNode.props):  # type: ignore[valid-type,misc]
        """Binds the annotation skin and adds the note's text and the control-pin switch."""

        REDRAW_FIELDS = BaseNode.props.REDRAW_FIELDS + ("text", "show_control_pins")

        # Bound by registry-key string: importing the skin would pull nicegui
        # onto the headless execution path.
        skin = setting[CHOICES](
            "haywire-core:skin:AnnotationSkin",
            label="Skin",
            description="Annotation nodes use the annotation skin",
            category="appearance",
            order=10,
        )
        text = setting[STRING](
            "",
            label="Text",
            description="What the note says; double-click the card to edit it",
            category="annotation",
            order=1,
        )
        show_control_pins = setting[BOOL](
            False,
            label="Show Control Pins",
            description="Draw the control pins while they are unlinked",
            category="annotation",
            order=2,
        )

    def init(self) -> None:
        from haywire.barn.builtin.types import ADD, ANNOTATION, EXEC

        self.add(EXEC.as_inlet("exec"))
        self.add(EXEC.as_outlet("done"))
        for side in self.SIDES:
            self._add_slot(side, 0, ADD[ANNOTATION])

    def worker(self, context: ExecutionContext) -> str:
        self.out("done", self.value("exec"))
        return "done"

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @classmethod
    def side_of(cls, port_id: str) -> str | None:
        """Return the card side *port_id* sits on, or ``None`` for a port on no side."""
        parsed = cls._parse(port_id)
        return parsed[0] if parsed is not None else None

    @classmethod
    def _parse(cls, port_id: str) -> tuple[str, int] | None:
        """The side and index *port_id* records (``right_2``), or ``None``."""
        side, _, index = port_id.partition("_")
        if side not in cls.SIDES or not index.isdigit():
            return None
        return side, int(index)

    def _grow(self, port: DataPort, edge_wrapper: EdgeWrapper) -> None:
        """Turn the connected slot into an annotation pin and open a new slot after it."""
        from haywire.barn.builtin.types import ADD, ANNOTATION

        # on_connect fires again on every re-link (load, paste, revalidation),
        # which must not grow a second slot.
        if port.type_cls is None or not issubclass(port.type_cls, ADD):
            return
        parsed = self._parse(port.id)
        if parsed is None:
            return
        side, index = parsed
        with self.rejig(include=[port.id]):
            self._add_slot(side, index, ANNOTATION, PortOrigin.RESOLVED)
        self._add_slot(side, self._next_index(side), ADD[ANNOTATION])

    def release_pins(self, port_ids: list[str]) -> list[str]:
        """Remove the annotation pins among *port_ids* that hold no arrow, and return their ids."""
        from haywire.barn.builtin.types import ADD
        from haywire.core.node.promotion import remove_port

        released = []
        for port_id in dict.fromkeys(port_ids):
            port = self.ports.get(port_id)
            # Open slots and the control pair are not grown pins.
            if port is None or self._parse(port_id) is None or port.is_linked():
                continue
            if port.type_cls is None or issubclass(port.type_cls, ADD):
                continue
            if remove_port(self, port_id):
                released.append(port_id)
        return released

    def restore_pins(self, port_ids: list[str]) -> None:
        """Grow the pins ``release_pins()`` removed back at their old ids."""
        from haywire.barn.builtin.types import ANNOTATION

        for port_id in port_ids:
            parsed = self._parse(port_id)
            if parsed is not None and port_id not in self.ports:
                self._add_slot(parsed[0], parsed[1], ANNOTATION, PortOrigin.RESOLVED)

    def _next_index(self, side: str) -> int:
        """One past the highest index in use on *side*.

        Indices are never reused: a port id is part of the id of every edge on it.
        """
        used = [
            parsed[1]
            for port_id in self.ports
            if (parsed := self._parse(port_id)) is not None and parsed[0] == side
        ]
        return max(used) + 1 if used else 0

    def _add_slot(self, side: str, index: int, itype: Any, origin: PortOrigin | None = None) -> None:
        """Add one swinglet of *itype* at *index* on *side*."""
        kwargs = {} if origin is None else {"origin": origin}
        self.add(
            itype.as_swinglet(
                id=f"{side}_{index}", label=f"{side.title()} {index}", on_connect="_grow", **kwargs
            )
        )
