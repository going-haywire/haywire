# haywire/core/settings/builtins/node_instance.py
"""
Node instance settings (local-only, per-node).

These settings are specific to each node instance and don't have
global equivalents. They control per-node UI state and behavior.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..holder import SettingsHolder


# Note: These are LOCAL_ONLY settings, defined here for documentation
# but actually registered per-node in SettingsHolder.
# This module provides the canonical list and helper for registration.

NODE_INSTANCE_SETTINGS = {
    'node.skin': {
        'default': None,
        'label': 'Skin',
        'description': 'Skin used for this node',
        'category': 'node.state',
    },
    'node.muted': {
        'default': False,
        'label': 'Muted',
        'description': 'Skip this node during execution',
        'category': 'node.state',
    },
    'node.collapsed': {
        'default': False,
        'label': 'Collapsed',
        'description': 'Collapse node to show only header',
        'category': 'node.state',
    },
    'node.condensed': {
        'default': False,
        'label': 'Condensed',
        'description': 'Show node in condensed view',
        'category': 'node.state',
    },
    'node.pinned': {
        'default': False,
        'label': 'Pinned',
        'description': 'Prevent auto-layout from moving this node',
        'category': 'node.state',
    },
    'node.color_override': {
        'default': None,
        'label': 'Color Override',
        'description': 'Custom background color for this node (None = use global)',
        'category': 'node.appearance',
        'ui_widget': 'color',
    },
    'node.comment': {
        'default': '',
        'label': 'Comment',
        'description': 'Comment displayed above the node',
        'category': 'node.annotation',
    },
    'node.show_comment': {
        'default': False,
        'label': 'Show Comment',
        'description': 'Display the comment bubble',
        'category': 'node.annotation',
    },
}


def register_node_instance_settings(holder: 'SettingsHolder') -> None:
    """
    Register local-only settings for a node instance.
    
    Called during node initialization to set up per-node settings.
    
    Args:
        holder: The node's SettingsHolder instance
    """
    from ..enums import SettingScope
    
    for name, config in NODE_INSTANCE_SETTINGS.items():
        holder.define(
            name,
            default=config['default'],
            scope=SettingScope.LOCAL_ONLY,
            label=config.get('label'),
            description=config.get('description', ''),
            category=config.get('category', 'node'),
            ui_widget=config.get('ui_widget'),
        )