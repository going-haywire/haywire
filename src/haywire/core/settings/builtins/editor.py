# haywire/core/settings/builtins/editor.py
"""
Editor behavior settings.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry


CATEGORY = 'editor'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register editor behavior settings."""
    
    # Undo/Redo
    registry.define(
        'editor.undo_limit', 100,
        label='Undo Limit',
        description='Maximum number of undo steps',
        category=CATEGORY,
        min_value=10,
        max_value=1000,
        ui_order=10
    )
    registry.define(
        'editor.group_undo_actions', True,
        label='Group Undo Actions',
        description='Group related actions into single undo step',
        category=CATEGORY,
        ui_order=11
    )
    
    # Auto-save
    registry.define(
        'editor.auto_save', True,
        label='Auto Save',
        description='Automatically save changes',
        category=CATEGORY,
        ui_order=20
    )
    registry.define(
        'editor.auto_save_interval_seconds', 60,
        label='Auto Save Interval (s)',
        description='Seconds between auto-saves',
        category=CATEGORY,
        min_value=10,
        max_value=600,
        ui_order=21
    )
    registry.define(
        'editor.create_backups', True,
        label='Create Backups',
        description='Create backup files before saving',
        category=CATEGORY,
        ui_order=22
    )
    registry.define(
        'editor.max_backups', 5,
        label='Max Backups',
        description='Maximum number of backup files to keep',
        category=CATEGORY,
        min_value=1,
        max_value=50,
        ui_order=23
    )
    
    # Selection and interaction
    registry.define(
        'editor.confirm_delete', True,
        label='Confirm Delete',
        description='Ask for confirmation when deleting nodes',
        category=CATEGORY,
        ui_order=30
    )
    registry.define(
        'editor.select_on_create', True,
        label='Select on Create',
        description='Select newly created nodes',
        category=CATEGORY,
        ui_order=31
    )
    registry.define(
        'editor.focus_on_create', True,
        label='Focus on Create',
        description='Pan canvas to show newly created nodes',
        category=CATEGORY,
        ui_order=32
    )
    registry.define(
        'editor.multi_select_modifier', 'ctrl',
        label='Multi-Select Modifier',
        description='Key modifier for multi-selection',
        category=CATEGORY,
        choices=['ctrl', 'shift', 'alt'],
        ui_order=33
    )
    
    # Mouse controls
    registry.define(
        'editor.pan_button', 'middle',
        label='Pan Mouse Button',
        description='Mouse button for canvas panning',
        category=CATEGORY,
        choices=['left', 'middle', 'right'],
        ui_order=40
    )
    registry.define(
        'editor.context_menu_button', 'right',
        label='Context Menu Button',
        description='Mouse button for context menu',
        category=CATEGORY,
        choices=['right', 'middle'],
        ui_order=41
    )
    registry.define(
        'editor.double_click_action', 'edit',
        label='Double Click Action',
        description='Action when double-clicking a node',
        category=CATEGORY,
        choices=['edit', 'collapse', 'inspect', 'none'],
        ui_order=42
    )
    
    # Clipboard
    registry.define(
        'editor.copy_with_connections', True,
        label='Copy with Connections',
        description='Include internal connections when copying multiple nodes',
        category=CATEGORY,
        ui_order=50
    )
    registry.define(
        'editor.paste_offset', 20,
        label='Paste Offset',
        description='Offset in pixels when pasting nodes',
        category=CATEGORY,
        min_value=0,
        max_value=100,
        ui_order=51
    )
    
    # Node creation
    registry.define(
        'editor.quick_add_enabled', True,
        label='Enable Quick Add',
        description='Enable quick node creation with spacebar',
        category=CATEGORY,
        ui_order=60
    )
    registry.define(
        'editor.quick_add_key', 'space',
        label='Quick Add Key',
        description='Key to open quick add menu',
        category=CATEGORY,
        choices=['space', 'tab', 'a'],
        ui_order=61
    )
    registry.define(
        'editor.show_recent_nodes', True,
        label='Show Recent Nodes',
        description='Show recently used nodes in quick add menu',
        category=CATEGORY,
        ui_order=62
    )
    registry.define(
        'editor.recent_nodes_count', 10,
        label='Recent Nodes Count',
        description='Number of recent nodes to show',
        category=CATEGORY,
        min_value=3,
        max_value=30,
        ui_order=63
    )