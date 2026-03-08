# haywire/core/settings/builtins/node_instance.py
"""
NodeInstanceSettings — per-node-instance settings schema.

Every node automatically receives these settings as an extra schema injected
into its SettingsHolder.  They are stored in the graph when locally set and
participate in the normal global resolution chain (so project-wide defaults
can be enforced via TOML or OVERRIDE mode).

Full keys:  node.skin, node.muted, node.collapsed, …
Access via: self.settings.skin,  self.settings.muted, …
"""

from haywire.core.settings.schema import NodeSettings
from haywire.core.settings.descriptors import setting
from haywire.core.settings.types import Color


class NodeInstanceSettings(NodeSettings, namespace='node'):
    """
    Framework-provided settings available on every node instance.

    These are injected as an extra schema in SettingsHolder so that every node
    exposes them alongside its own class-defined Settings.
    """

    skin: str | None = setting(
        None,
        label='Skin',
        category='node.state',
        description='Skin used for this node',
    )
    muted: bool = setting(
        False,
        label='Muted',
        category='node.state',
        description='Skip this node during execution',
    )
    collapsed: bool = setting(
        False,
        label='Collapsed',
        category='node.state',
        description='Collapse node to show only header',
    )
    condensed: bool = setting(
        False,
        label='Condensed',
        category='node.state',
        description='Show node in condensed view',
    )
    pinned: bool = setting(
        False,
        label='Pinned',
        category='node.state',
        description='Prevent auto-layout from moving this node',
    )
    color_override: Color | None = setting(
        None,
        label='Color Override',
        category='node.appearance',
        description='Custom background color for this node (None = use theme default)',
        widget='color',
    )
    comment: str = setting(
        '',
        label='Comment',
        category='node.annotation',
        description='Comment displayed above the node',
    )
    show_comment: bool = setting(
        False,
        label='Show Comment',
        category='node.annotation',
        description='Display the comment bubble',
    )
