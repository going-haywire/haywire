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

from haywire.core.settings.descriptor import shadow
from haywire.core.settings.settings_graph import GraphSettings
from haywire.core.skin.settings import (
    NodeDefaultSkinSettings,
    _layout_direction_choices,
    _node_skin_choices,
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
