# haywire/core/graph/properties.py
"""GraphProperties — framework-provided per-graph props (``graph.props``).

Each field here shadows a framework setting, and a node-bag field may mirror
one with ``graph(src=<field here>)``, interposing the graph tier between the
framework default and a node's own opinion: framework < graph < node.

Serialized under the ``'props'`` key in graph JSON; restored before nodes
on load.
"""

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
        # A mirror inherits its IType from src but not src's widget_config, so
        # the options have to be repeated on every field below.
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
