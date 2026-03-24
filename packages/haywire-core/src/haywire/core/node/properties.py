# haywire/core/settings/builtins/node_instance.py
"""
NodeInstanceSettings — per-node-instance observable props.

Migrated from NodeSettings + setting() to Reactive + prop().
No longer part of the Settings resolution chain.

Access via:  node.props.muted,  node.props.collapsed, ...
Serialized under the 'props' key in graph JSON.
"""

from haywire.core.property import Bag, prop


class NodeProperties(Bag):
    """
    Framework-provided props available on every node instance.

    Accessed as ``node.props`` (e.g. ``self.props.muted``).
    Serialized under ``'props'`` key in the graph JSON.
    """

    # -----------------------------------------------------------------
    # Visual state
    # -----------------------------------------------------------------

    muted: bool = prop(
        False,
        label="Muted",
        order=10,
        category="state",
        description="Skip this node during execution",
    )
    collapsed: bool = prop(
        False,
        label="Collapsed",
        order=20,
        category="state",
        description="Collapse node to show only header",
    )
    condensed: bool = prop(
        False,
        label="Condensed",
        order=30,
        category="state",
        description="Show node in condensed view",
    )
    pinned: bool = prop(
        False,
        label="Pinned",
        order=40,
        category="state",
        description="Prevent auto-layout from moving this node",
    )

    # -----------------------------------------------------------------
    # Appearance
    # -----------------------------------------------------------------

    skin: str | None = prop(
        None,
        label="Skin",
        order=10,
        category="appearance",
        description="Skin used for this node",
    )
    color_override: str | None = prop(
        None,
        label="Color Override",
        order=20,
        category="appearance",
        description="Custom background color for this node (None = use theme default)",
        widget="color",
    )

    # -----------------------------------------------------------------
    # Annotation
    # -----------------------------------------------------------------

    comment: str = prop(
        "",
        label="Comment",
        order=10,
        category="annotation",
        description="Comment displayed above the node",
    )
    show_comment: bool = prop(
        False,
        label="Show Comment",
        order=20,
        category="annotation",
        description="Display the comment bubble",
    )

    # -----------------------------------------------------------------
    # Layout (position & dimensions) — not shown in settings panels
    # -----------------------------------------------------------------

    posX: float = prop(0.0, order=10, category="layout")
    posY: float = prop(0.0, order=20, category="layout")
    width: float = prop(0.0, order=30, category="layout")
    height: float = prop(0.0, order=40, category="layout")
    width_min: float = prop(-1.0, order=50, category="layout")
    height_min: float = prop(-1.0, order=60, category="layout")

    # -----------------------------------------------------------------
    # Convenience helpers
    # -----------------------------------------------------------------

    def set_position(self, pos: tuple[float, float]) -> None:
        """Set node position as (x, y) tuple."""
        self.posX = pos[0]
        self.posY = pos[1]

    def get_position(self) -> tuple[float, float]:
        """Get node position as (x, y) tuple."""
        return (self.posX, self.posY)
