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

    Accessed as ``node.props`` (e.g. ``self.props.muted``).
    Serialized under ``'props'`` key in the graph JSON.
    """

    REDRAW_FIELDS: tuple[str, ...] = (
        "muted",
        "collapsed",
        "detail",
        "pinned",
        "skin",
        "layout_direction",
        "comment",
    )
    """Fields whose change triggers a full node-card redraw.

    NodeWrapper subscribes to these after each build; layout fields
    (posX/posY/width/height/…) are deliberately absent — position changes
    ride the cheaper NODE_MOVED path and fire on every drag tick.

    ``collapsed`` and ``detail`` belong here for a reason specific to them:
    both are CONSTRUCTION gates, so a change must rebuild the card rather than
    restyle it. Hiding with CSS would leave every element built, mounted and
    re-walked, which is the cost the axes exist to avoid (ADR 0032, ADR 0006).

    So are the two appearance fields (``node_theme``, ``color_override``):
    both resolve to CSS custom properties written onto the node's host slot,
    which the browser re-resolves without the card being rebuilt. Redrawing for
    a colour is what destroyed the input being typed into.
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
    collapsed = graph(
        src=GraphProperties.collapsed,
        label="Collapsed",
        order=20,
        category="state",
        description="Fold to card, title, badges and the pins of linked ports",
    )
    # `condensed` lived here from introduction until 2026-08-30, read by no
    # skin the whole time. It named a middle density between collapsed and
    # full, which is now `detail` — resolved through three tiers instead of
    # being a per-node bool nobody wired. See ADR 0032.
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
    #
    # `None` is the whole "unset" mechanism: emptiness means inherit, so there
    # is no need to ask whether the field was *locally set*. It is written as a
    # --hw-node-bg declaration on the node's host slot, composed AFTER any node
    # theme's tokens so an explicit highlight always wins, and cleared by
    # emptying the field. Alpha rides inside the value as #rrggbbaa (COLOR is
    # "hex or rgba" — see ColorStr), so a translucent highlight needs no second
    # field.
    #
    # Deliberately absent from REDRAW_FIELDS: this is a style-write on a stable
    # element, never a card rebuild. See UINode._apply_slot_style.
    color_override = setting[COLOR](
        None,
        label="Color Override",
        order=20,
        category="appearance",
        description="Custom background color for this node (empty = use the theme's)",
        widget_config={"alpha": True},
    )

    # -----------------------------------------------------------------
    # Annotation
    # -----------------------------------------------------------------

    # Emptiness is the whole visibility mechanism — the same bargain
    # `color_override` makes. A node with text gets a badge beside its
    # diagnostics badge, at the COLLAPSED tier so an annotation stays readable
    # on a folded node; a node without text gets nothing. The old companion
    # `show_comment` bool bought exactly "no badge", which an empty comment
    # already gives, and was rendered by no skin in its entire life (ADR 0032).
    comment = setting[STRING](
        "",
        label="Comment",
        order=10,
        category="annotation",
        description="Note shown as a badge on the node; hover the badge to read it",
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
    # style-write — see UINode._apply_slot_style (no card redraw). width/height stay
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
