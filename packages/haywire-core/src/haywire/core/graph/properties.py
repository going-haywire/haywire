# haywire/core/graph/properties.py
"""
GraphProperties — framework-provided per-graph props (``graph.props``).

The graph-side analogue of NodeProperties. Fields here interpose the graph
tier between framework defaults and per-node opinions: each field shadows
a framework setting (registry-key mirror), and node-bag fields may declare
``graph(src=<field here>)`` (graph mirror), yielding framework < graph <
node.

Serialized under the ``'props'`` key in graph JSON; restored before nodes
on load.
"""

from haywire.barn.builtin.types import BOOL
from haywire.core.settings import setting
from haywire.core.settings.descriptor import shadow
from haywire.core.settings.settings_graph import GraphSettings
from haywire.core.skin.settings import (
    NodeDefaultSkinSettings,
    _layout_direction_choices,
    _node_detail_choices,
    _node_skin_choices,
    _node_theme_choices,
)


class GraphProperties(GraphSettings):
    """Framework props available on every graph as ``graph.props``."""

    default_skin = shadow(
        src=NodeDefaultSkinSettings.studio_skin,
        label="Default Node Skin",
        description=(
            "Default skin for nodes in THIS graph. Overrides the studio "
            "default; a node's own skin setting overrides this."
        ),
        category="appearance",
        order=10,
        # Mirrors inherit IType (-> CHOICES/SELECT_WIDGET) from src, but NOT
        # its per-setting widget_config — options must be re-supplied here.
        widget_config={"options": _node_skin_choices},
    )

    layout_direction = shadow(
        src=NodeDefaultSkinSettings.studio_layout_direction,
        label="Layout Direction",
        description=(
            "Flow direction for nodes in THIS graph. Overrides the studio "
            "default; a node's own layout direction overrides this."
        ),
        category="appearance",
        order=20,
        widget_config={"options": _layout_direction_choices},
    )

    detail = shadow(
        src=NodeDefaultSkinSettings.studio_node_detail,
        label="Node Detail",
        description=(
            "How much of a node card is drawn in THIS graph. Overrides the "
            "studio default; a node's own detail overrides this."
        ),
        category="appearance",
        order=25,
        widget_config={"options": _node_detail_choices},
    )

    # Two tiers only (graph < node), so no shadow(): a framework-tier fold would
    # open every graph showing nothing, while THIS field persists in the
    # .haywire file, which is where "this graph is large" belongs. ADR 0032.
    collapsed = setting[BOOL](
        False,
        label="Nodes Collapsed",
        description=(
            "Fold nodes in THIS graph to card, title, badges and linked pins. "
            "A node that has been folded or unfolded by hand keeps its own state."
        ),
        category="appearance",
        order=27,
    )

    node_theme = shadow(
        src=NodeDefaultSkinSettings.studio_node_theme,
        label="Node Theme",
        description=(
            "Theme for the node cards in THIS graph. Overrides the studio "
            "default; a node's own theme overrides this."
        ),
        category="appearance",
        order=30,
        widget_config={"options": _node_theme_choices},
    )
