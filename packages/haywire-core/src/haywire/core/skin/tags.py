"""The tags a skin carries in ``SkinIdentity.tags``, which the skin choice lists filter on.

A skin without tags is general. See ``haywire.core.skin.settings.skin_choices``.
"""

#: A skin for any node, offered in the general skin lists.
SKIN_TAG_GENERAL = "general"
#: A skin for one kind of node only; the general lists leave it out.
SKIN_TAG_SPECIAL = "special"
#: A skin meant for the stage view; the patch skin lists leave it out.
SKIN_TAG_STAGE_ONLY = "stage-only"
#: A skin for widget nodes; offered only in a widget node's stage skin list.
SKIN_TAG_WIDGET_NODE = "widget-node"
#: A skin for Graph-nodes (Groups and macro placements); offered only in their skin lists.
SKIN_TAG_GRAPH_NODE = "graph-node"
