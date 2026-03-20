# haywire/core/settings/builtins/node_instance.py
"""
NodeInstanceSettings — per-node-instance observable props.

Migrated from NodeSettings + setting() to Reactive + prop().
No longer part of the Settings resolution chain.

Access via:  node.props.muted,  node.props.collapsed, ...
Serialized under the 'props' key in graph JSON.
"""

from haywire.core.reactive import Reactive, prop


class NodeInstanceSettings(Reactive):
    """
    Framework-provided props available on every node instance.

    Accessed as ``node.props`` (e.g. ``self.props.muted``).
    Serialized under ``'props'`` key in the graph JSON.
    """

    skin: str | None = prop(
        None,
        label='Skin',
        category='node.state',
        description='Skin used for this node',
    )
    muted: bool = prop(
        False,
        label='Muted',
        category='node.state',
        description='Skip this node during execution',
    )
    collapsed: bool = prop(
        False,
        label='Collapsed',
        category='node.state',
        description='Collapse node to show only header',
    )
    condensed: bool = prop(
        False,
        label='Condensed',
        category='node.state',
        description='Show node in condensed view',
    )
    pinned: bool = prop(
        False,
        label='Pinned',
        category='node.state',
        description='Prevent auto-layout from moving this node',
    )
    color_override: str | None = prop(
        None,
        label='Color Override',
        category='node.appearance',
        description='Custom background color for this node (None = use theme default)',
        widget='color',
    )
    comment: str = prop(
        '',
        label='Comment',
        category='node.annotation',
        description='Comment displayed above the node',
    )
    show_comment: bool = prop(
        False,
        label='Show Comment',
        category='node.annotation',
        description='Display the comment bubble',
    )
