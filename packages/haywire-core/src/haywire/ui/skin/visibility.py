"""Node visibility — what a card draws, resolved once per render.

Composes the two ADR-0032 axes (**Node collapse** and **NodeDetail**) with
**Group collapse** and port link state into a single value object that skins
ask questions of:

.. code-block:: python

    show = self.show_of(wrapper)
    for port in show.ports(node):
        ...
    if show.label:
        ui.label(port.label).classes("text-xs zoom-pan-lod2")

The point of the indirection is that the rank→element mapping lives **here and
nowhere else**. A skin never compares ranks, so re-tiering later — moving
labels from FULL to STANDARD, say — is a change to this module rather than an
edit to every skin.

Lives in core (not in the studio skin package) for the same reason
``pin_render`` does: a standalone skin that does not subclass ``NodeSkin``
still needs to resolve the axes. ``NodeSkin.show_of()`` is a thin wrapper over
:func:`resolve_node_visibility`.

**Advisory, not enforced.** A skin that ignores this renders everything: slower,
never broken — the same posture ``render_pin`` takes for ``LayoutDirection``.
See ADR 0032 decision 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from haywire.core.types import NodeDetail

if TYPE_CHECKING:
    from haywire.core.node.data import NodeData
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.types import DataPort


@dataclass(frozen=True)
class NodeVisibility:
    """What one node's card draws, for one render.

    A pure value: it holds no node reference and no per-node state, which is
    what makes it safe to build inside a ``SkinFactory``-cached skin (one
    instance per registry key, shared across every node in every open graph).

    The predicates are **properties, not methods**, deliberately: ``if
    show.label:`` on a method is silently always true, and this whole object
    exists to make a class of silent rendering bug impossible.
    """

    collapsed: bool
    """Whether the card is folded to title, badges and linked pins."""

    detail: NodeDetail
    """Density rank of the card when it is not folded."""

    # ------------------------------------------------------------------
    # What to draw
    # ------------------------------------------------------------------

    @property
    def label(self) -> bool:
        """Port labels. FULL only — pin and config-row tooltips already carry
        identification, and a label is one element per port."""
        return not self.collapsed and self.detail.includes(NodeDetail.FULL)

    @property
    def widget(self) -> bool:
        """Inline port widgets, and the group toggles that are themselves
        widgets. STANDARD and above."""
        return not self.collapsed and self.detail.includes(NodeDetail.STANDARD)

    @property
    def diagnostics(self) -> bool:
        """Inline diagnostics detail — the alternate-versions notice and the
        eagerly-built error menu body. FULL only.

        NOT the badge: a badge is drawn at every rank, folded included, because
        a node nobody can see is broken is worse than a slow one.
        """
        return not self.collapsed and self.detail.includes(NodeDetail.FULL)

    # ------------------------------------------------------------------
    # Which ports to draw
    # ------------------------------------------------------------------

    def ports(self, node: "NodeData") -> List["DataPort"]:
        """The ports this card renders, in display order.

        A filter rather than a boolean because this is where Node collapse,
        Group collapse and link state all meet, and duplicating that three-way
        composition into every skin is how the three drift apart.

        **Folded**: every *linked* port, whatever its group state. Group
        collapse is ignored on purpose — an edge must always find its endpoint,
        and a folded card is all header, so there is nowhere else for a hidden
        port's pin to go. Unlinked ports are dropped, which is what makes a
        folded 23-port node actually small. Sections and group control ports
        are excluded, matching ``iter_hidden_connected_ports``; a group control
        port is never linked, so it falls out anyway.

        **Unfolded**: exactly today's answer, ``get_visible_ports()`` — the
        detail rank changes what is drawn *per port*, not which ports exist.
        Callers still consult ``get_hidden_connected_ports()`` for the header
        pins of group-hidden connected ports, unchanged.
        """
        if not self.collapsed:
            return node.get_visible_ports()
        return [
            port
            for port in node.get_all_ports()
            if not port.section and not port.is_group and port.is_linked()
        ]


def resolve_node_visibility(wrapper: "NodeWrapper") -> NodeVisibility:
    """Resolve both card axes for *wrapper*, through framework < graph < node.

    Reads ``node.props.collapsed`` and ``node.props.detail``, whose mirrors
    already resolve their chains. Anything unexpected degrades — ``coerce``
    falls to FULL, an unreadable ``collapsed`` falls to unfolded — because this
    runs on the render path and must never take a node card down. Degrading
    toward *more* drawing is deliberate: a card that draws too much costs
    performance, one that draws too little looks broken.

    A pure function of the wrapper, never stored on the skin: ``SkinFactory``
    caches one skin instance per registry key across every node in every open
    graph.
    """
    try:
        props = wrapper.node.props
    except Exception:
        return NodeVisibility(collapsed=False, detail=NodeDetail.FULL)

    try:
        collapsed = bool(props.collapsed)
    except Exception:
        collapsed = False

    try:
        detail = NodeDetail.coerce(props.detail)
    except Exception:
        detail = NodeDetail.FULL

    return NodeVisibility(collapsed=collapsed, detail=detail)
