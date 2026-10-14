"""Per-node-instance observable props.

Read and written as ``node.props.locked``, ``node.props.collapsed``, …, and
serialized under the ``'props'`` key in the graph JSON.
"""

from haywire.core.settings import NodeSettings, setting
from haywire.core.settings.descriptor import graph
from haywire.core.graph.properties import GraphProperties
from haywire.core.node.layout import PATCH, LayoutChannel
from haywire.core.skin.settings import (
    _layout_direction_choices,
    _node_detail_choices,
    _node_skin_choices,
    _node_theme_choices,
)
from haywire.barn.builtin.types import BOOL, CHOICES, COLOR, INT, FLOAT, STRING


class NodeProperties(NodeSettings):
    """
    Framework-provided props available on every node instance.

    Accessed as ``node.props`` (e.g. ``self.props.locked``).
    Serialized under ``'props'`` key in the graph JSON.
    """

    REDRAW_FIELDS: tuple[str, ...] = (
        "collapsed",
        "locked",
        "skin",
        "layout_direction",
        "comment",
        "label",
    )
    """Fields whose change triggers a full node-card redraw.

    ``NodeWrapper`` subscribes to these after each build. A field belongs here
    only when its change alters what the card builds: ``collapsed`` gates
    construction, so it does.

    Layout fields (posX/posY/width/height) stay out — a position change rides
    the cheaper NODE_MOVED path (a drag sends its positions once, at drag end), and a size change
    is a style-write on the host slot. ``detail`` stays out because a rank
    change is a CSS class flip, not a rebuild (ADR 0032), as do ``node_theme``
    and ``color_override``, which resolve to CSS custom properties the browser
    re-reads in place.
    """

    # -----------------------------------------------------------------
    # Annotation
    # -----------------------------------------------------------------
    #
    # Resolution lives in one place: `NodeData.display_label`.
    label = setting[STRING](
        "",
        label="Label",
        order=5,
        category="annotation",
        description="Name for this node, replacing its class label (empty = use the class label)",
    )

    comment = setting[STRING](
        "",
        label="Comment",
        order=10,
        category="annotation",
        description="Note shown as a badge on the node; hover the badge to read it",
    )

    # -----------------------------------------------------------------
    # Visual state
    # -----------------------------------------------------------------

    collapsed = setting[BOOL](
        False,
        label="Collapsed",
        order=20,
        category="state",
        description="Fold to card, title, badges and the pins of linked ports",
    )

    locked = setting[BOOL](
        False,
        label="Locked",
        order=40,
        category="state",
        description="Protect this node from being moved, resized or deleted by accident",
    )

    # -----------------------------------------------------------------
    # Appearance
    # -----------------------------------------------------------------

    skin = graph(
        src=GraphProperties.default_skin,
        label="Skin",
        category="appearance",
        order=10,
        # A mirror inherits its IType (-> CHOICES/SELECT_WIDGET) from src but not
        # src's widget_config, so the options are re-supplied here.
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

    detail = graph(
        src=GraphProperties.detail,
        label="Detail",
        description="How much of THIS node's card is drawn. Overrides the graph's.",
        category="appearance",
        order=16,
        widget_config={"options": _node_detail_choices},
    )

    node_theme = graph(
        src=GraphProperties.node_theme,
        label="Node Theme",
        description="Theme for THIS node's card. Overrides the graph's.",
        category="appearance",
        order=17,
        widget_config={"options": _node_theme_choices},
    )

    # A single colour that replaces the card's background, whatever produced it
    # — the workbench theme, a node theme, or a skin's own default.
    color_override = setting[COLOR](
        None,
        label="Color Override",
        order=20,
        category="appearance",
        description="Custom background color for this node (empty = use the theme's)",
        widget_config={"alpha": True},
    )

    # -----------------------------------------------------------------
    # Layout (position & dimensions) — shown in the node Properties panel
    # -----------------------------------------------------------------

    posX = setting[FLOAT](0.0, order=10, category="layout")
    posY = setting[FLOAT](0.0, order=20, category="layout")
    # A valid pair from birth (200/200 bootstraps a headless node). size_adapt
    # discriminates per axis: an "auto" axis is measured from the render and
    # written back, a "manual" axis is fixed by the user's resize gadget. Both
    # apply as a style-write on the host slot, with no card redraw.
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

    def set_position(self, pos: tuple[float, float], channel: LayoutChannel = PATCH) -> None:
        """Set the position, as an ``(x, y)`` tuple, in the channel's fields."""
        setattr(self, channel.x, pos[0])
        setattr(self, channel.y, pos[1])

    def get_position(self, channel: LayoutChannel = PATCH) -> tuple[float, float]:
        """Return the position, as an ``(x, y)`` tuple, from the channel's fields."""
        return (getattr(self, channel.x), getattr(self, channel.y))
