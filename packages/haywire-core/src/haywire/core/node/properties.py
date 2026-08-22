# haywire/core/settings/builtins/node_instance.py
"""
NodeInstanceSettings — per-node-instance observable props.

Migrated from NodeSettings + setting() to Settings + setting().
No longer part of the Settings resolution chain.

Access via:  node.props.muted,  node.props.collapsed, ...
Serialized under the 'props' key in graph JSON.
"""

from haywire.core.settings import NodeSettings, setting
from haywire.core.settings.descriptor import graph
from haywire.core.graph.properties import GraphProperties
from haywire.core.skin.settings import _layout_direction_choices, _node_skin_choices
from haywire.barn.builtin.types import BOOL, CHOICES, COLOR, INT, FLOAT, STRING


class NodeProperties(NodeSettings):
    """
    Framework-provided props available on every node instance.

    Accessed as ``node.props`` (e.g. ``self.props.muted``).
    Serialized under ``'props'`` key in the graph JSON.
    """

    REDRAW_FIELDS: tuple[str, ...] = (
        "muted",
        "collapsed",
        "condensed",
        "pinned",
        "skin",
        "layout_direction",
        "color_override",
        "comment",
        "show_comment",
    )
    """Fields whose change triggers a full node-card redraw.

    NodeWrapper subscribes to these after each build; layout fields
    (posX/posY/width/height/…) are deliberately absent — position changes
    ride the cheaper NODE_MOVED path and fire on every drag tick.
    """

    # -----------------------------------------------------------------
    # Visual state
    # -----------------------------------------------------------------

    muted = setting[BOOL](
        False,
        label="Muted",
        order=10,
        category="state",
        description="Mark this node as muted (execution skipping not yet implemented)",
    )
    collapsed = setting[BOOL](
        False,
        label="Collapsed",
        order=20,
        category="state",
        description="Collapse node to show only header",
    )
    condensed = setting[BOOL](
        False,
        label="Condensed",
        order=30,
        category="state",
        description="Show node in condensed view",
    )
    pinned = setting[BOOL](
        False,
        label="Pinned",
        order=40,
        category="state",
        description="Prevent auto-layout from moving this node",
    )

    # -----------------------------------------------------------------
    # Appearance
    # -----------------------------------------------------------------

    skin = graph(
        src=GraphProperties.default_skin,
        label="Skin",
        category="appearance",
        order=10,
        # Mirrors inherit IType (-> CHOICES/SELECT_WIDGET) from src, but NOT its
        # per-setting widget_config — options must be re-supplied here.
        widget_config={"options": _node_skin_choices},
    )

    layout_direction = graph(
        src=GraphProperties.layout_direction,
        label="Layout Direction",
        description="Direction flow reads across THIS node's card",
        category="appearance",
        order=15,
        widget_config={"options": _layout_direction_choices},
    )

    color_override = setting[COLOR](
        None,
        label="Color Override",
        order=20,
        category="appearance",
        description="Custom background color for this node (None = use theme default)",
    )

    # -----------------------------------------------------------------
    # Annotation
    # -----------------------------------------------------------------

    comment = setting[STRING](
        "",
        label="Comment",
        order=10,
        category="annotation",
        description="Comment displayed above the node",
    )
    show_comment = setting[BOOL](
        False,
        label="Show Comment",
        order=20,
        category="annotation",
        description="Display the comment bubble",
    )

    # -----------------------------------------------------------------
    # Layout (position & dimensions) — not shown in settings panels
    # -----------------------------------------------------------------

    posX = setting[FLOAT](0.0, order=10, category="layout")
    posY = setting[FLOAT](0.0, order=20, category="layout")
    # Size — a valid pair from birth (200/200 bootstrap for headless nodes).
    # size_adapt discriminates per axis: an "auto" axis is measured from render
    # (written back by the ResizeObserver in ui_node.py); a "manual" axis is
    # fixed by the user's resize gadget. Applied to the host slot as a
    # style-write — see UINode._apply_size (no card redraw). width/height stay
    # OUT of REDRAW_FIELDS.
    width = setting[INT](200, order=30, category="layout")
    height = setting[INT](200, order=40, category="layout")
    size_adapt = setting[CHOICES](
        "auto",
        widget_config={
            "options": {
                "auto": "Auto",
                "manual_width": "Manual width · auto height",
                "manual_height": "Manual height · auto width",
                "manual": "Manual (both)",
            }
        },
        label="Size Adapt",
        description="Per-axis manual control of node card size",
        order=50,
        category="layout",
    )

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
